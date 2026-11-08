# acima-unit: payments
"""Violation D005 (half): Payments reaches back into Orders."""
from acima.orders.impl.module import OrdersModule

ORDERS = OrdersModule
