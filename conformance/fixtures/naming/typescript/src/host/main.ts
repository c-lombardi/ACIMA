// Compliant naming: domain responsibility rather than generic roles.
class OrderValidator {
  validate(order: unknown): boolean {
    return Boolean(order);
  }
}

interface OrderRepository {
  findById(orderId: string): unknown;
}

class PaymentAuthorizer {
  authorize(payment: unknown): boolean {
    return Boolean(payment);
  }
}
