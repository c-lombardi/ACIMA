"""D012: a default argument hides a decision the caller should make."""


def create_order(repository: object, send_notification: bool = True) -> None:
    repository.save(send_notification)
