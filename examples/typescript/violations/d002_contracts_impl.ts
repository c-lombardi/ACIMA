// acima-unit: orders.contracts
import { CatalogModule } from '../src/catalog/impl/module.ts';

/** A contract reaching into an implementation. */
export interface SneakyOrder {
  readonly catalog: CatalogModule;
}
