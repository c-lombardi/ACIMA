"""The aggregate. Mutable on purpose: immutability is a boundary rule, not an internal one."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from acima.orders.contracts import OrderLine, OrderSummary
from acima.shared_kernel import Currency, Money, OrderId


@dataclass
class Order:
    """An order being assembled. `total` is derived, never set from outside."""

    id: OrderId
    customer_id: str
    lines: list[OrderLine] = field(default_factory=list)

    def add(self, line: OrderLine) -> None:
        self.lines.append(line)

    @property
    def total(self) -> Money:
        currency = self.lines[0].unit_price.currency if self.lines else Currency.EUR
        return Money(
            sum((line.unit_price.amount * line.quantity for line in self.lines), Decimal("0")),
            currency,
        )

    def to_summary(self) -> OrderSummary:
        return OrderSummary(
            id=self.id,
            customer_id=self.customer_id,
            total=self.total,
            lines=tuple(self.lines),
        )
