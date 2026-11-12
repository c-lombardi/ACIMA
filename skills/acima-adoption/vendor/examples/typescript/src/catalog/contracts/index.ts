/**
 * Catalog's complete public surface. Zero external dependencies.
 * The boundary is this file: nothing under `impl/` is exported from it.
 */
import type { Money, ProductId } from './values.ts';

export { Money, productId } from './values.ts';
export type { Currency, OrderId, PaymentId, ProductId } from './values.ts';

/** A purchasable product. `price` is the current list price. */
export interface ProductView {
  readonly id: ProductId;
  readonly name: string;
  readonly price: Money;
}

/** The capability Catalog promises. */
export interface CatalogReader {
  get(productId: ProductId): ProductView | undefined;
  listAll(): readonly ProductView[];
}
