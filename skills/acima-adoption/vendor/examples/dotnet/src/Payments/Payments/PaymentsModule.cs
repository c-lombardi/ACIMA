using Acima.Payments.Contracts;

namespace Acima.Payments;

internal sealed class FakeGateway(decimal declineAbove) : IPaymentGateway
{
    public PaymentAuthorization Authorize(PaymentRequest request) =>
        request.Amount.Amount > declineAbove
            ? new PaymentAuthorization(Approved: false, PaymentId: null, Reference: null)
            : new PaymentAuthorization(
                Approved: true,
                PaymentId: new PaymentId(Value: Guid.NewGuid().ToString("n")),
                Reference: "ref-" + Guid.NewGuid().ToString("n")[..8]);

    public void Refund(PaymentId paymentId, Money amount)
    {
        if (string.IsNullOrEmpty(paymentId.Value))
        {
            throw new ArgumentException("refund needs a payment id", nameof(paymentId));
        }
    }
}

/// <summary>Payments' composition surface.</summary>
public sealed class PaymentsModule
{
    /// <summary>Builds Payments with a fake gateway that declines above the threshold.</summary>
    public PaymentsModule(decimal declineAbove) => Port = new FakeGateway(declineAbove: declineAbove);

    /// <summary>The port other modules consume.</summary>
    public IPaymentGateway Port { get; }
}
