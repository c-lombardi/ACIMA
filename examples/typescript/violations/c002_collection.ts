// acima-unit: payments.contracts
/** A collection in a message. */
export interface PaymentBatch {
  readonly payments: PaymentBatchItem[];
  readonly total: number;
}

/** One item. */
export interface PaymentBatchItem { readonly id: string; }
