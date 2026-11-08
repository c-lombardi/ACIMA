// acima-unit: shared-kernel
import type { ProductView } from '../src/catalog/contracts/index.ts';

/** A kernel that is not a leaf. */
export interface KernelProduct {
  readonly view: ProductView;
}
