// acima-unit: payments.contracts
namespace Acima.Payments.Contracts;

/// <summary>A batch that can be rewritten by its consumer.</summary>
public sealed record PaymentBatch(List<string> Payments);
