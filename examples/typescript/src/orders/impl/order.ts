import type { OrderLine, OrderSummary } from '../contracts/index.ts';
import type { Money, OrderId } from '../../shared-kernel/money.ts';

/**
 * The aggregate. Mutable on purpose: immutability is a boundary rule, not an internal one.
 */
export class Order {
  private readonly lines: OrderLine[] = [];

  readonly id: OrderId;
  readonly customerId: string;
  private readonly currency: Money;

  constructor(id: OrderId, customerId: string, currency: Money) {
    this.id = id;
    this.customerId = customerId;
    this.currency = currency;
  }

  add(line: OrderLine): void {
    this.lines.push(line);
  }

  get total(): Money {
    return this.lines.reduce(
      (sum, line) => sum.plus(line.unitPrice.times(line.quantity)),
      this.currency.times(0),
    );
  }

  toSummary(): OrderSummary {
    return {
      id: this.id,
      customerId: this.customerId,
      total: this.total,
      lines: [...this.lines],
    };
  }
}
