namespace Acima.Catalog.Contracts;

/// <summary>The currencies this contract accepts.</summary>
public enum Currency
{
    /// <summary>Euro.</summary>
    Eur,

    /// <summary>US dollar.</summary>
    Usd,
}

/// <summary>An immutable amount of money. Construct through <see cref="Of"/>.</summary>
public readonly struct Money
{
    private Money(decimal amount, Currency currency)
    {
        Amount = amount;
        Currency = currency;
    }

    /// <summary>The amount, in major units, quantised to cents.</summary>
    public decimal Amount { get; }

    /// <summary>The currency.</summary>
    public Currency Currency { get; }

    /// <summary>Creates a validated amount.</summary>
    public static Money Of(decimal amount, Currency currency)
    {
        if (amount < 0m)
        {
            throw new ArgumentOutOfRangeException(nameof(amount), "money cannot be negative");
        }

        if (decimal.Round(amount, 2) != amount)
        {
            throw new ArgumentException("money must be quantised to cents", nameof(amount));
        }

        return new Money(amount, currency);
    }

    /// <summary>The zero amount in a currency.</summary>
    public static Money Zero(Currency currency) => Of(0m, currency);

    /// <summary>Multiplies by a non-negative whole quantity.</summary>
    public Money Times(int quantity) => quantity < 0
        ? throw new ArgumentOutOfRangeException(nameof(quantity), "quantity cannot be negative")
        : Of(Amount * quantity, Currency);

    /// <summary>Adds another amount of the same currency.</summary>
    public Money Plus(Money other) => other.Currency != Currency
        ? throw new ArgumentException("currency mismatch", nameof(other))
        : Of(Amount + other.Amount, Currency);

    /// <inheritdoc />
    public bool Equals(Money other) => Amount == other.Amount && Currency == other.Currency;

    /// <inheritdoc />
    public override int GetHashCode() => HashCode.Combine(Amount, Currency);

    /// <inheritdoc />
    public override string ToString() => $"{Amount:0.00} {Currency.ToString().ToUpperInvariant()}";

    /// <summary>Equality operator.</summary>
    public static bool operator ==(Money left, Money right) => left.Equals(right);

    /// <summary>Inequality operator.</summary>
    public static bool operator !=(Money left, Money right) => !left.Equals(right);
}

/// <summary>Identifies a product in this contract's vocabulary.</summary>
public readonly record struct ProductId(string Value);

/// <summary>Identifies an order in this contract's vocabulary.</summary>
public readonly record struct OrderId(string Value);

/// <summary>Identifies a payment in this contract's vocabulary.</summary>
public readonly record struct PaymentId(string Value);
