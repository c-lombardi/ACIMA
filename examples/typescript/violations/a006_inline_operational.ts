// Deliberately broken: an operational policy value is embedded inline.

export function reserve(): number {
  const retryLimit = 3;
  return retryLimit;
}
