// Deliberately broken: non-idiomatic type casing and a generic responsibility name.
class order_validator {
  validate(order: unknown): boolean {
    return Boolean(order);
  }
}

class OrderHelper {
  validate(order: unknown): boolean {
    return Boolean(order);
  }
}
