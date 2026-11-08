/**
 * The composition root. The only place where every module is known.
 * Run: node src/host/main.ts
 */
import { Money, productId } from '../shared-kernel/money.ts';
import { CatalogModule } from '../catalog/impl/module.ts';
import { OrdersModule } from '../orders/impl/module.ts';
import { PaymentsModule } from '../payments/impl/module.ts';

const catalog = new CatalogModule();
const payments = new PaymentsModule();
const orders = new OrdersModule(catalog.reader(), payments.port());

catalog.add({ id: productId('p-1'), name: 'Espresso beans', price: new Money(12.5, 'EUR') });
catalog.add({ id: productId('p-2'), name: 'Filter papers', price: new Money(3.2, 'EUR') });

const result = orders.place({
  customerId: 'c-1',
  lines: [
    { productId: productId('p-1'), unitPrice: new Money(12.5, 'EUR'), quantity: 2 },
    { productId: productId('p-2'), unitPrice: new Money(3.2, 'EUR'), quantity: 1 },
  ],
});

console.log('placed:', result);
console.log('events:', orders.events().map((e) => ('reason' in e ? 'OrderRejected' : 'OrderPlaced')));
