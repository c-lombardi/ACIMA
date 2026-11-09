"""Compliant: required values arrive from the composition boundary."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OrdersSettings:
    retry_limit: int


class OrdersService:
    def __init__(self, settings: OrdersSettings, endpoint: str) -> None:
        self._settings = settings
        self._endpoint = endpoint

    def describe(self) -> str:
        return f"{self._endpoint}:{self._settings.retry_limit}"
