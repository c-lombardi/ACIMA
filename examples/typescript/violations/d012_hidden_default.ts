/** D012: a default argument hides a decision the caller should make. */
function createOrder(repository: { save(value: boolean): void }, sendNotification = true): void {
  repository.save(sendNotification);
}
