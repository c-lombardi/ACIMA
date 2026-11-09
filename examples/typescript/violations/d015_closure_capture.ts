// Deliberately broken: a function captures a module-level application dependency.
class OrderRepository {
  save(request: unknown): unknown {
    return request;
  }
}

const orderRepository = new OrderRepository();

export const createOrder = (request: unknown) => orderRepository.save(request);
