import type { CatalogReader } from '../../catalog/contracts/index.ts';
import type { PaymentGateway } from '../../payments/contracts/index.ts';
import { Money, orderId } from '../contracts/index.ts';
import type {
  OrderId, OrderLine, OrderPlaced, OrderRejected, OrderSummary, PlaceOrder, RejectionReason,
} from '../contracts/index.ts';
import { Money as PaymentMoney } from '../../payments/contracts/index.ts';
import { Order } from './order.ts';

/** Orders' application service. Depends only on contracts and its own domain. */
export class OrdersModule {
  private readonly orders = new Map<string, Order>();
  private readonly published: Array<OrderPlaced | OrderRejected> = [];

  private readonly catalog: CatalogReader;
  private readonly payments: PaymentGateway;
  private readonly now: () => Date;

  constructor(catalog: CatalogReader, payments: PaymentGateway, now: () => Date = () => new Date()) {
    this.catalog = catalog;
    this.payments = payments;
    this.now = now;
  }

  place(command: PlaceOrder): OrderSummary | OrderRejected {
    const id = orderId(crypto.randomUUID());
    const lines: OrderLine[] = [];

    for (const line of command.lines) {
      const product = this.catalog.get(line.productId);
      if (product === undefined) return this.reject(id, 'out_of_stock');
      lines.push({
        productId: line.productId,
        unitPrice: new Money(product.price.amount, product.price.currency),
        quantity: line.quantity,
      });
    }

    const order = new Order(id, command.customerId, lines[0]!.unitPrice.times(0));
    for (const line of lines) order.add(line);

    const authorization = this.payments.authorize({
      orderId: id,
      amount: new PaymentMoney(order.total.amount, order.total.currency),
      customerId: command.customerId,
    });
    if (!authorization.approved) return this.reject(id, 'payment_declined');

    this.orders.set(id.value, order);
    const summary = order.toSummary();
    this.published.push({
      orderId: id,
      customerId: summary.customerId,
      total: summary.total,
      lines: summary.lines,
    });
    return summary;
  }

  get(id: OrderId): OrderSummary | undefined {
    return this.orders.get(id.value)?.toSummary();
  }

  recent(limit: number): readonly OrderSummary[] {
    return [...this.orders.values()].slice(-limit).reverse().map((o) => o.toSummary());
  }

  events(): readonly (OrderPlaced | OrderRejected)[] {
    return [...this.published];
  }

  private reject(id: OrderId, reason: RejectionReason): OrderRejected {
    const rejected: OrderRejected = { orderId: id, reason };
    this.published.push(rejected);
    return rejected;
  }
}
