"""Value-ownership fixture for A006.

The two MAX_*_ATTEMPTS declarations are different policies with the same literal.
The two MAX_RETRY_ATTEMPTS declarations are candidate duplicates.
"""

from typing import Final

MAX_ORDER_ATTEMPTS: Final = 3
MAX_PAYMENT_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_TIMEOUT_MILLISECONDS = 30000
ORDER_API_URL = "https://orders.example.test"
DB_PASSWORD = "not-a-real-secret"


class OrderPolicy:
    MAX_RETRY_ATTEMPTS = 3
    CACHE_TTL_SECONDS = 60


class PaymentPolicy:
    MAX_RETRY_ATTEMPTS = 3


def dispatch(order: str, retry_limit: int, request_timeout: int) -> str:
    return order


def submit(order: str, request_timeout: int) -> str:
    return dispatch(order, 3, request_timeout)


def submit_with_timeout(order: str, retry_limit: int) -> str:
    return dispatch(order, retry_limit, 30)


def mutable_policy(order: str) -> str:
    retry_limit = 3
    return dispatch(order, retry_limit, 60)


def incidental() -> int:
    total = 0
    for index, line in enumerate(range(3)):
        total += index
    return total
