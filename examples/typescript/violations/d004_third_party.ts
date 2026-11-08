// acima-unit: catalog.contracts
import { z } from 'zod';

/** A contract that validates itself. */
export interface Validated {
  readonly name: string;
}

export const schema = z.object({ name: z.string() });
