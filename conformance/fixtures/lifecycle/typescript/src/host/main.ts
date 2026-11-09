// Compliant lifecycle choices: shared stateless, scoped request, transient identity.
class OrderValidator {
  validate(order: unknown): boolean {
    return Boolean(order);
  }
}

class RequestContext {}

class OrdersService {
  constructor(private readonly context: RequestContext) {}
}

class IdGenerator {
  private sequence = 0;
}

class SqlClient {
  private connection: unknown = null;

  close(): void {
    this.connection = null;
  }
}

register(OrderValidator, { lifetime: 'singleton' });
register(RequestContext, { lifetime: 'scoped' });
register(OrdersService, { lifetime: 'scoped' });
register(IdGenerator, { lifetime: 'transient' });
register(SqlClient, { lifetime: 'singleton' });
