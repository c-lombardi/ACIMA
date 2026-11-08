/**
 * Value types owned by this contracts project. No imports outside the language core.
 *
 * Duplicated in each module's contracts package on purpose: value types belong to the
 * boundary that publishes them, not to a shared kernel.
 */
export type Currency = 'EUR' | 'USD' | 'GBP';

/** An immutable amount in one currency, quantised to cents. */
export class Money {
  readonly amount: number;
  readonly currency: Currency;

  constructor(amount: number, currency: Currency) {
    if (!Number.isFinite(amount)) throw new TypeError('amount must be finite');
    if (amount < 0) throw new RangeError('money cannot be negative');
    if (Math.round(amount * 100) !== amount * 100) throw new RangeError('money must be quantised');
    this.amount = amount;
    this.currency = currency;
  }

  times(quantity: number): Money {
    if (!Number.isInteger(quantity) || quantity < 0) throw new RangeError('bad quantity');
    return new Money(this.amount * quantity, this.currency);
  }

  plus(other: Money): Money {
    if (other.currency !== this.currency) throw new RangeError('currency mismatch');
    return new Money(this.amount + other.amount, this.currency);
  }

  toString(): string {
    return `${this.amount.toFixed(2)} ${this.currency}`;
  }
}

/** Strongly typed identifiers in this module's vocabulary. */
export interface ProductId { readonly value: string; }
/** A typed order identifier; it prevents accidental cross-module identity mixing. */
export interface OrderId { readonly value: string; }
/** A typed payment identifier; it prevents accidental cross-module identity mixing. */
export interface PaymentId { readonly value: string; }

export const productId = (value: string): ProductId => ({ value });
export const orderId = (value: string): OrderId => ({ value });
export const paymentId = (value: string): PaymentId => ({ value });
