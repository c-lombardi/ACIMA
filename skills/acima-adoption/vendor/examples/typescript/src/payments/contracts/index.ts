/**
 * Payments' public surface: a port, a request and a result. No framework types, no money
 * arithmetic beyond the contract value type, no persistence.
 */
import type { Money, OrderId, PaymentId } from './values.ts';

export { Money, paymentId } from './values.ts';
export type { Currency, OrderId, PaymentId, ProductId } from './values.ts';

/** Command: authorize this amount for this order. */
export interface PaymentRequest {
  readonly orderId: OrderId;
  readonly amount: Money;
  readonly customerId: string;
}

/** Result: whether the gateway authorized, and the reference for reconciliation. */
export interface PaymentAuthorization {
  readonly approved: boolean;
  readonly paymentId?: PaymentId;
  readonly reference?: string;
}

/** The capability Payments promises. */
export interface PaymentGateway {
  authorize(request: PaymentRequest): PaymentAuthorization;
  refund(paymentId: PaymentId, amount: Money): void;
}
