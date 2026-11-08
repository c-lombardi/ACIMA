using Acima.Catalog.Contracts;
using Acima.Orders.Contracts;
using Acima.Payments.Contracts;
using Acima.SharedKernel;

namespace Acima.Orders;

internal sealed class Order(OrderId id, string customerId, Money zero)
{
    private readonly List<OrderLine> _lines = new();
    private Money _total = zero;

    public OrderId Id => id;

    public void Add(OrderLine line)
    {
        _lines.Add(line);
        _total = _total.Plus(line.UnitPrice.Times(line.Quantity));
    }

    public OrderSummary Summary() => new(id, customerId, _lines.ToArray(), _total);
}

/// <summary>Orders' composition surface.</summary>
public sealed class OrdersModule
{
    private readonly ICatalogReader _catalog;
    private readonly IPaymentGateway _payments;
    private readonly Dictionary<string, Order> _orders = new(StringComparer.Ordinal);
    private readonly List<object> _published = new();

    /// <summary>Wires Orders to the ports the host provides.</summary>
    public OrdersModule(ICatalogReader catalog, IPaymentGateway payments)
    {
        _catalog = catalog;
        _payments = payments;
    }

    /// <summary>Runs the place-order workflow.</summary>
    public PlaceOrderResult Place(PlaceOrder command)
    {
        var id = new OrderId(Guid.NewGuid().ToString("n"));
        var lines = new List<OrderLine>();
        foreach (var line in command.Lines)
        {
            var product = _catalog.Get(line.ProductId);
            if (product is null)
            {
                return Reject(id, RejectionReason.OutOfStock);
            }

            lines.Add(new OrderLine(line.ProductId, product.Price, line.Quantity));
        }

        if (lines.Count == 0)
        {
            throw new ArgumentException("an order needs at least one line", nameof(command));
        }

        var order = new Order(id, command.CustomerId, Money.Zero(lines[0].UnitPrice.Currency));
        foreach (var line in lines)
        {
            order.Add(line);
        }

        var authorization = _payments.Authorize(new PaymentRequest(id, order.Summary().Total, command.CustomerId));
        if (!authorization.Approved)
        {
            return Reject(id, RejectionReason.PaymentDeclined);
        }

        _orders[id.Value] = order;
        var summary = order.Summary();
        _published.Add(new OrderPlaced(id, summary.CustomerId, summary.Total));
        return new PlaceOrderResult(summary, null);
    }

    /// <summary>Returns an accepted order.</summary>
    public OrderSummary? Get(OrderId id) => _orders.TryGetValue(id.Value, out var order) ? order.Summary() : null;

    /// <summary>The events published so far.</summary>
    public IReadOnlyList<object> Published => _published;

    private PlaceOrderResult Reject(OrderId id, RejectionReason reason)
    {
        var rejected = new OrderRejected(id, reason);
        _published.Add(rejected);
        return new PlaceOrderResult(null, rejected);
    }
}
