// acima-unit: catalog.contracts
import { catalog } from '../src/host/main.ts';

/** A contract that knows its host. */
export interface HostBound {
  readonly module: typeof catalog;
}
