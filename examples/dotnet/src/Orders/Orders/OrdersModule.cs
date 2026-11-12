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
        _total = _total.Plus(other: line.UnitPrice.Times(quantity: line.Quantity));
    }

    public OrdersContracts.OrderSummary Summary() => new(Id: id, CustomerId: customerId, Lines: _lines.ToArray(), Total: _total);
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
        var id = new OrdersContracts.OrderId(Value: Guid.NewGuid().ToString("n"));
        var lines = new List<OrdersContracts.OrderLine>();
        foreach (var line in command.Lines)
        {
            var product = _catalog.Get(id: new CatalogContracts.ProductId(Value: line.ProductId.Value));
            if (product is null)
            {
                return Reject(id: id, reason: OrdersContracts.RejectionReason.OutOfStock);
            }

            var price = OrdersContracts.Money.Of(
                amount: product.Price.Amount,
                currency: (OrdersContracts.Currency)product.Price.Currency);
            lines.Add(new OrdersContracts.OrderLine(ProductId: line.ProductId, UnitPrice: price, Quantity: line.Quantity));
        }

        if (lines.Count == 0)
        {
            throw new ArgumentException("an order needs at least one line", nameof(command));
        }

        var order = new Order(id: id, customerId: command.CustomerId, zero: OrdersContracts.Money.Zero(currency: lines[0].UnitPrice.Currency));
        foreach (var line in lines)
        {
            order.Add(line: line);
        }

        var summary = order.Summary();
        var amount = PaymentsContracts.Money.Of(
            amount: summary.Total.Amount,
            currency: (PaymentsContracts.Currency)summary.Total.Currency);
        var authorization = _payments.Authorize(request: new PaymentsContracts.PaymentRequest(
            OrderId: new PaymentsContracts.OrderId(Value: id.Value),
            Amount: amount,
            CustomerId: command.CustomerId));
        if (!authorization.Approved)
        {
            return Reject(id: id, reason: OrdersContracts.RejectionReason.PaymentDeclined);
        }

        _orders[id.Value] = order;
        _published.Add(new OrdersContracts.OrderPlaced(OrderId: id, CustomerId: summary.CustomerId, Total: summary.Total));
        return new OrdersContracts.PlaceOrderResult(Accepted: summary, Rejected: null);
    }

    /// <summary>Returns an accepted order.</summary>
    public OrdersContracts.OrderSummary? Get(OrdersContracts.OrderId id) =>
        _orders.TryGetValue(id.Value, out var order) ? order.Summary() : null;

    /// <summary>The events published so far.</summary>
    public IReadOnlyList<object> Published => _published;

    private OrdersContracts.PlaceOrderResult Reject(OrdersContracts.OrderId id,
        OrdersContracts.RejectionReason reason)
    {
        var rejected = new OrdersContracts.OrderRejected(OrderId: id, Reason: reason);
        _published.Add(rejected);
        return new OrdersContracts.PlaceOrderResult(Accepted: null, Rejected: rejected);
    }
}
