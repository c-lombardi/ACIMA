"""Deliberately broken: a component receives a dependency through an injected field."""


class Inject:
    def __class_getitem__(cls, item):
        return cls


class OrdersService:
    repository: Inject["Repository"]
