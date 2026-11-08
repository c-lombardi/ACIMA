// acima-unit: orders.contracts
import type { ProductView } from '../src/catalog/contracts/index.ts';

/** A contract that depends on another module's contract. */
export interface SneakyLine {
  readonly product: ProductView;
}
