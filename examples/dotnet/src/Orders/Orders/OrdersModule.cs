using CatalogContracts = Acima.Catalog.Contracts;
using OrdersContracts = Acima.Orders.Contracts;
using PaymentsContracts = Acima.Payments.Contracts;

namespace Acima.Orders;

internal sealed class Order(OrdersContracts.OrderId id, string customerId, OrdersContracts.Money zero)
{
    private readonly List<OrdersContracts.OrderLine> _lines = new();
    private OrdersContracts.Money _total = zero;

    public OrdersContracts.OrderId Id => id;

    public void Add(OrdersContracts.OrderLine line)
    {
        _lines.Add(line);
        _total = _total.Plus(line.UnitPrice.Times(line.Quantity));
    }

    public OrdersContracts.OrderSummary Summary() => new(id, customerId, _lines.ToArray(), _total);
}

/// <summary>Orders' composition surface.</summary>
public sealed class OrdersModule
{
    private readonly CatalogContracts.ICatalogReader _catalog;
    private readonly PaymentsContracts.IPaymentGateway _payments;
    private readonly Dictionary<string, Order> _orders = new(StringComparer.Ordinal);
    private readonly List<object> _published = new();

    /// <summary>Wires Orders to the ports the host provides.</summary>
    public OrdersModule(CatalogContracts.ICatalogReader catalog, PaymentsContracts.IPaymentGateway payments)
    {
        _catalog = catalog;
        _payments = payments;
    }

    /// <summary>Runs the place-order workflow.</summary>
    public OrdersContracts.PlaceOrderResult Place(OrdersContracts.PlaceOrder command)
    {
        var id = new OrdersContracts.OrderId(Guid.NewGuid().ToString("n"));
        var lines = new List<OrdersContracts.OrderLine>();
        foreach (var line in command.Lines)
        {
            var product = _catalog.Get(new CatalogContracts.ProductId(line.ProductId.Value));
            if (product is null)
            {
                return Reject(id, OrdersContracts.RejectionReason.OutOfStock);
            }

            var price = OrdersContracts.Money.Of(
                product.Price.Amount,
                (OrdersContracts.Currency)product.Price.Currency);
            lines.Add(new OrdersContracts.OrderLine(line.ProductId, price, line.Quantity));
        }

        if (lines.Count == 0)
        {
            throw new ArgumentException("an order needs at least one line", nameof(command));
        }

        var order = new Order(id, command.CustomerId, OrdersContracts.Money.Zero(lines[0].UnitPrice.Currency));
        foreach (var line in lines)
        {
            order.Add(line);
        }

        var summary = order.Summary();
        var amount = PaymentsContracts.Money.Of(
            summary.Total.Amount,
            (PaymentsContracts.Currency)summary.Total.Currency);
        var authorization = _payments.Authorize(new PaymentsContracts.PaymentRequest(
            new PaymentsContracts.OrderId(id.Value),
            amount,
            command.CustomerId));
        if (!authorization.Approved)
        {
            return Reject(id, OrdersContracts.RejectionReason.PaymentDeclined);
        }

        _orders[id.Value] = order;
        _published.Add(new OrdersContracts.OrderPlaced(id, summary.CustomerId, summary.Total));
        return new OrdersContracts.PlaceOrderResult(summary, null);
    }

    /// <summary>Returns an accepted order.</summary>
    public OrdersContracts.OrderSummary? Get(OrdersContracts.OrderId id) =>
        _orders.TryGetValue(id.Value, out var order) ? order.Summary() : null;

    /// <summary>The events published so far.</summary>
    public IReadOnlyList<object> Published => _published;

    private OrdersContracts.PlaceOrderResult Reject(OrdersContracts.OrderId id,
        OrdersContracts.RejectionReason reason)
    {
        var rejected = new OrdersContracts.OrderRejected(id, reason);
        _published.Add(rejected);
        return new OrdersContracts.PlaceOrderResult(null, rejected);
    }
}
