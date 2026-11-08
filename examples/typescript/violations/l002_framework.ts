// acima-unit: orders.contracts
import { Router } from 'express';

/** A contract that speaks HTTP. */
export interface OrderRoute {
  readonly router: Router;
}
