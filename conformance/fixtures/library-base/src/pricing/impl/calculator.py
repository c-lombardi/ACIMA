"""Private implementation. The package consumer composes it; no host is required."""

from pricing.contracts.quote import Quote


def create_quote(amount: int) -> Quote:
    return Quote(amount=amount)
