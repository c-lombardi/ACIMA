"""Strongly typed identifiers. Identity primitives are the kernel's second legitimate use."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProductId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("product id cannot be empty")


@dataclass(frozen=True, slots=True)
class OrderId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("order id cannot be empty")


@dataclass(frozen=True, slots=True)
class PaymentId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("payment id cannot be empty")
