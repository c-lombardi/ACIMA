"""A framework may activate this controller; its dependency is still explicit."""

from orders.service import OrdersService


class OrdersController:
    def __init__(self, orders: OrdersService) -> None:
        self._orders = orders

    def place(self) -> str:
        return "accepted"
