"""Compliant naming: domain responsibility rather than generic roles."""


class OrderValidator:
    def validate(self, order):
        return bool(order)


class PaymentAuthorizer:
    def authorize(self, payment):
        return bool(payment)


class OrderRepository:
    def find_by_id(self, order_id):
        return None
