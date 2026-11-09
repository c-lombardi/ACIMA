"""D011: an optional constructor parameter is a second construction path."""


class _PaymentService:
    def charge(self, amount: int) -> None:
        return None


class OrderService:
    def __init__(self, repository: object, payments: _PaymentService | None = None) -> None:
        self._repository = repository
        self._payments = payments
