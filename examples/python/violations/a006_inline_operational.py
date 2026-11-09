"""Deliberately broken: an operational policy value is embedded inline."""


def reserve() -> int:
    retry_limit = 3
    return retry_limit
