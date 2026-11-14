// Deliberately broken: lifecycle choices hide statelessness, scope and mutable state.
class LifecycleOrderValidator {
  validate(order: unknown): boolean {
    return Boolean(order);
  }
}

class LifecycleRequestContext {}

class LifecycleInjectedService {
  constructor(private readonly context: LifecycleRequestContext) {}
}

class LifecycleOrdersService {
  constructor(private readonly context: LifecycleRequestContext) {}
}

class LifecyclePriceCache {
  private values = new Map<string, number>();
}

register(LifecycleOrderValidator, { lifetime: 'transient' });
register(LifecycleRequestContext, { lifetime: 'scoped' });
register(LifecycleInjectedService, { lifetime: 'transient' });
register(LifecycleOrdersService, { lifetime: 'singleton' });
register(LifecyclePriceCache, { lifetime: 'singleton' });
