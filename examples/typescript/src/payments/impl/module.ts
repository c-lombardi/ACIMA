import type {
  Money, PaymentAuthorization, PaymentGateway, PaymentId, PaymentRequest,
} from '../contracts/index.ts';
import { paymentId } from '../contracts/index.ts';

/** A fake gateway: deterministic, testable, and replaceable without touching Payments. */
export class FakeGateway implements PaymentGateway {
  private readonly refunded = new Set<string>();

  private readonly declineAbove: number;

  constructor(declineAbove: number) {
    this.declineAbove = declineAbove;
  }

  authorize(request: PaymentRequest): PaymentAuthorization {
    if (request.amount.amount > this.declineAbove) return { approved: false };
    return {
      approved: true,
      paymentId: paymentId(crypto.randomUUID()),
      reference: `ref-${crypto.randomUUID().slice(0, 8)}`,
    };
  }

  refund(id: PaymentId, _amount: Money): void {
    this.refunded.add(id.value);
  }
}

/** Payments' composition function. */
export class PaymentsModule {
  private readonly gateway: PaymentGateway;

  constructor(gateway: PaymentGateway = new FakeGateway(1000)) {
    this.gateway = gateway;
  }

  port(): PaymentGateway {
    return this.gateway;
  }
}
