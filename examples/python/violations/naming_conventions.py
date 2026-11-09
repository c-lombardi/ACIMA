# Deliberately broken: non-idiomatic type casing and a generic responsibility name.
class order_validator:
    def validate(self, order):
        return bool(order)


class OrderHelper:
    def validate(self, order):
        return bool(order)
