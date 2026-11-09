/** D011: an optional constructor parameter is a second construction path. */
class PaymentService {
  charge(_amount: number): void {}
}

class OrderService {
  private readonly repository: object;

  constructor(repository: object, payments?: PaymentService) {
    this.repository = repository;
    void payments;
  }
}
