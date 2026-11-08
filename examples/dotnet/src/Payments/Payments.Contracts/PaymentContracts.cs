using Acima.SharedKernel;

namespace Acima.Payments.Contracts;

/// <summary>Asks the gateway to authorize an amount for an order.</summary>
public sealed record PaymentRequest(OrderId OrderId, Money Amount, string CustomerId);

/// <summary>The gateway's answer.</summary>
public sealed record PaymentAuthorization(bool Approved, PaymentId? PaymentId, string? Reference);

/// <summary>The capability Payments promises.</summary>
public interface IPaymentGateway
{
    /// <summary>Authorizes the requested amount.</summary>
    PaymentAuthorization Authorize(PaymentRequest request);

    /// <summary>Refunds a settled payment.</summary>
    void Refund(PaymentId paymentId, Money amount);
}
