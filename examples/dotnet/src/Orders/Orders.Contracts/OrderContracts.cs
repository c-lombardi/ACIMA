using Acima.SharedKernel;

namespace Acima.Orders.Contracts;

/// <summary>One product in one order, with the price captured at placement time.</summary>
public sealed record OrderLine(ProductId ProductId, Money UnitPrice, int Quantity);

/// <summary>Asks Orders to place an order.</summary>
public sealed record PlaceOrder(string CustomerId, IReadOnlyList<OrderLine> Lines);

/// <summary>What Orders returns about an accepted order.</summary>
public sealed record OrderSummary(OrderId Id, string CustomerId, IReadOnlyList<OrderLine> Lines, Money Total);

/// <summary>Emitted when an order is accepted and paid for.</summary>
public sealed record OrderPlaced(OrderId OrderId, string CustomerId, Money Total);

/// <summary>The closed set of reasons an order can be refused.</summary>
public enum RejectionReason
{
    /// <summary>A product was unknown or unavailable.</summary>
    OutOfStock,

    /// <summary>The gateway refused the authorization.</summary>
    PaymentDeclined,
}

/// <summary>Emitted when an order is refused.</summary>
public sealed record OrderRejected(OrderId OrderId, RejectionReason Reason);

/// <summary>The outcome of a place-order attempt: accepted or rejected.</summary>
public sealed record PlaceOrderResult(OrderSummary? Accepted, OrderRejected? Rejected);

/// <summary>The read capability Orders promises.</summary>
public interface IOrdersReader
{
    /// <summary>Returns an accepted order, or null.</summary>
    OrderSummary? Get(OrderId id);
}
