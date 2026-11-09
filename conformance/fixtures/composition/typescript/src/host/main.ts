// Compliant composition boundary: every component is constructed by name.
import { InMemoryRepository, OrdersService } from '../orders/service.ts';

export const orders = new OrdersService(new InMemoryRepository());
