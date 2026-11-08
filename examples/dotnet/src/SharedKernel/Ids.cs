namespace Acima.SharedKernel;

/// <summary>Identifies a product.</summary>
public readonly record struct ProductId(string Value);

/// <summary>Identifies an order.</summary>
public readonly record struct OrderId(string Value);

/// <summary>Identifies a payment.</summary>
public readonly record struct PaymentId(string Value);
