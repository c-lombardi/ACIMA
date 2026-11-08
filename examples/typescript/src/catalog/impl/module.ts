import type { CatalogReader, ProductId, ProductView } from '../contracts/index.ts';

/** In-memory product store. A database would implement the same class shape. */
export class InMemoryProductStore {
  private readonly rows = new Map<string, ProductView>();
  readonly table = 'catalog_products';

  find(id: ProductId): ProductView | undefined {
    return this.rows.get(id.value);
  }

  all(): readonly ProductView[] {
    return [...this.rows.values()].sort((a, b) => a.id.value.localeCompare(b.id.value));
  }

  save(product: ProductView): void {
    this.rows.set(product.id.value, product);
  }
}

/** Adapter that satisfies the provided port. Not exported from contracts. */
class CatalogReaderAdapter implements CatalogReader {
  private readonly store: InMemoryProductStore;

  constructor(store: InMemoryProductStore) {
    this.store = store;
  }

  get(productId: ProductId): ProductView | undefined {
    return this.store.find(productId);
  }

  listAll(): readonly ProductView[] {
    return this.store.all();
  }
}

/** The module: constructed with its dependencies, never discovering them. */
export class CatalogModule {
  private readonly store: InMemoryProductStore;
  private readonly adapter: CatalogReaderAdapter;

  constructor(store: InMemoryProductStore = new InMemoryProductStore()) {
    this.store = store;
    this.adapter = new CatalogReaderAdapter(store);
  }

  reader(): CatalogReader {
    return this.adapter;
  }

  add(product: ProductView): void {
    this.store.save(product);
  }
}
