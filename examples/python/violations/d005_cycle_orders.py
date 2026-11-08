# acima-unit: orders
"""Violation D005 (half): Orders reaches into Payments."""
from acima.payments.impl.gateway import FakeGateway

GATEWAY = FakeGateway
