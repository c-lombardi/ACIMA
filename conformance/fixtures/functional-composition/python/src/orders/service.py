"""Compliant: closures may capture a dependency that is an explicit outer parameter."""


class Repository:
    def save(self, request):
        return request


def create_order(repository, request):
    return repository.save(request)


def make_handler(repository):
    return lambda request: repository.save(request)


def apply_twice(transform, value):
    return transform(transform(value))
