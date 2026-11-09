"""Compliant lifecycle choices: shared stateless, scoped request, transient identity."""


class OrderValidator:
    def validate(self, order):
        return bool(order)


class RequestContext:
    pass


class OrdersService:
    def __init__(self, context: RequestContext):
        self._context = context


class IdGenerator:
    def __init__(self):
        self._sequence = 0


class SqlClient:
    def __init__(self):
        self._connection = None

    def close(self):
        self._connection = None


register(OrderValidator, lifetime="singleton")
register(RequestContext, lifetime="scoped")
register(OrdersService, lifetime="scoped")
register(IdGenerator, lifetime="transient")
register(SqlClient, lifetime="singleton")
