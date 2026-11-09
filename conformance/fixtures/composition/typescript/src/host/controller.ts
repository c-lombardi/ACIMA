// A framework may activate this controller; its dependency is still explicit.
import { OrdersService } from '../orders/service.ts';

export class OrdersController {
  constructor(private readonly orders: OrdersService) {}

  place(): string {
    return this.orders ? 'accepted' : 'unavailable';
  }
}
