// Deliberately broken: a component receives a dependency through property injection.

function Inject(_token: string): PropertyDecorator {
  return () => undefined;
}

class OrdersService {
  @Inject('repository')
  private repository!: unknown;
}

export { OrdersService };
