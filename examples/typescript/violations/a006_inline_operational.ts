// Deliberately broken: a meaningful value is passed inline and another binding is mutable.

function send(order: string, retryLimit: number): string {
  return order;
}

export function reserve(order: string): string {
  const retryLimit = 3;
  let fallbackLimit = 3;
  return send(order, 3) + retryLimit + fallbackLimit;
}
