/** Explicit inputs: every required input is supplied by the caller. */
interface PaymentGateway {
  charge(amount: number): void;
}

function createOrder(gateway: PaymentGateway, requestedDeliveryDate: Date | null): void {
  gateway.charge(requestedDeliveryDate === null ? 0 : 1);
}
