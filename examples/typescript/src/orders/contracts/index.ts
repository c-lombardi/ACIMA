/**
 * Orders' public surface. Zero dependencies beyond the shared kernel: no catalog types,
 * no payments types, no framework. Identity only, so the price is frozen at placement time.
 */
import type { Money, OrderId, ProductId } from '../../shared-kernel/money.ts';

/** One product in one order. `unitPrice` is captured when the order is placed. */
export interface OrderLine {
  readonly productId: ProductId;
  readonly unitPrice: Money;
  readonly quantity: number;
}

/** Command: place an order for a customer. */
export interface PlaceOrder {
  readonly customerId: string;
  readonly lines: readonly OrderLine[];
}

/** View: what Orders promises to return about an order. */
export interface OrderSummary {
  readonly id: OrderId;
  readonly customerId: string;
  readonly total: Money;
  readonly lines: readonly OrderLine[];
}

/** Event: an order was accepted and paid for. */
export interface OrderPlaced {
  readonly orderId: OrderId;
  readonly customerId: string;
  readonly total: Money;
  readonly lines: readonly OrderLine[];
}

/** The closed set of rejection reasons. */
export type RejectionReason = 'out_of_stock' | 'payment_declined';

/** Event: an order was refused, with a reason the business cares about. */
export interface OrderRejected {
  readonly orderId: OrderId;
  readonly reason: RejectionReason;
}

/** The capability Orders promises. */
export interface OrdersReader {
  get(orderId: OrderId): OrderSummary | undefined;
  recent(limit: number): readonly OrderSummary[];
}
