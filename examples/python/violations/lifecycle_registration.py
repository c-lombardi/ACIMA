"""Deliberately broken: lifecycle choices hide statelessness, scope and mutable state."""


class LifecycleOrderValidator:
    def validate(self, order):
        return bool(order)


class LifecycleRequestContext:
    pass


class LifecycleInjectedService:
    def __init__(self, context: LifecycleRequestContext):
        self._context = context


class LifecycleOrdersService:
    def __init__(self, context: LifecycleRequestContext):
        self._context = context


class LifecyclePriceCache:
    def __init__(self):
        self._values = {}


register(LifecycleOrderValidator, lifetime="transient")
register(LifecycleRequestContext, lifetime="scoped")
register(LifecycleInjectedService, lifetime="transient")
register(LifecycleOrdersService, lifetime="singleton")
register(LifecyclePriceCache, lifetime="singleton")
