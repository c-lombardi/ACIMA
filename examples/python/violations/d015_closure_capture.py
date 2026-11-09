"""Deliberately broken: a function captures a module-level application dependency."""


class OrderRepository:
    def save(self, request):
        return request


order_repository = OrderRepository()


def create_order(request):
    return order_repository.save(request)
