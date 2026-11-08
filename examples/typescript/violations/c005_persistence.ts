// acima-unit: payments.contracts
import type { DbContext } from 'zod';

/** A contract that leaks the database. */
export interface PaymentRow {
  readonly db: DbContext;
}
