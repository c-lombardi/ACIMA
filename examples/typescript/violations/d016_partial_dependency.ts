// Deliberately broken: a component pre-binds a module-owned dependency.
function save(orderRepository: unknown, request: unknown): unknown {
  return request;
}

export function makeHandler(orderRepository: unknown) {
  return save.bind(null, orderRepository);
}
