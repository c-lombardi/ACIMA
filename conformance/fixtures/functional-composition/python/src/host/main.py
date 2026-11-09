"""Compliant: dependencies are supplied by the composition boundary."""

from orders.service import Repository, create_order


def build():
    repository = Repository()
    return create_order(repository, "request")
