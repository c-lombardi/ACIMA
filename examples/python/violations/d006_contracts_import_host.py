# acima-unit: payments.contracts
"""Violation D006: contracts must not know how they are hosted."""
from acima.host.main import build

WIRE = build
