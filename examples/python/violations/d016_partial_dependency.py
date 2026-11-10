"""Deliberately broken: a component pre-binds a module-owned dependency."""

from functools import partial


def save(order_repository, request):
    return order_repository.save(request)


def make_handler(order_repository):
    return partial(save, order_repository)
