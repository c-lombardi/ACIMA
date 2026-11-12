"""Explicit inputs: every required input is supplied by the caller."""
from datetime import datetime


def create_order(repository: object, requested_delivery_date: datetime | None) -> object:
    """A nullable value without a default is still a required input."""
    return repository.create(requested_delivery_date)


def charge(gateway: object, amount: int) -> object:
    return gateway.charge(amount)


def submit_order(repository: object, requested_delivery_date: datetime | None) -> object:
    return create_order(repository=repository, requested_delivery_date=requested_delivery_date)
