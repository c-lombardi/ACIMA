# acima-unit: orders
"""D017: locally declared function and method calls must label their arguments."""


def create_order(request_id: str, customer_id: str, customer_name: str) -> tuple[str, str, str]:
    return request_id, customer_id, customer_name


class OrderRepository:
    def save(self, request_id: str, customer_id: str) -> tuple[str, str]:
        return request_id, customer_id


def process(repository: OrderRepository) -> None:
    create_order("r-1", "c-1", "Alice")
    repository.save("r-1", "c-1")
