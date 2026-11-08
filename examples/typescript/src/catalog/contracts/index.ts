/**
 * Catalog's complete public surface. Zero dependencies beyond the shared kernel.
 * The boundary is this file: nothing under `impl/` is exported from it.
 */
import type { Money, ProductId } from '../../shared-kernel/money.ts';

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
