// Compliant: dependencies are supplied by the composition boundary.
import { Repository, createOrder } from '../orders/service.ts';

const repository = new Repository();
export const result = createOrder(repository, 'request');
