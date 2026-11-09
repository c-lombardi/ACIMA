"""Compliant component: its dependency is a required constructor parameter."""


class InMemoryRepository:
    pass


class OrdersService:
    def __init__(self, repository: InMemoryRepository) -> None:
        self._repository = repository
