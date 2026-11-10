// Value-ownership fixture for A006.
// MAX_ORDER_ATTEMPTS and MAX_PAYMENT_ATTEMPTS have the same literal but different meanings.
// MAX_RETRY_ATTEMPTS is a candidate duplicate within and across files in this module.

export const MAX_ORDER_ATTEMPTS = 3;
export const MAX_PAYMENT_ATTEMPTS = 3;
export const REQUEST_TIMEOUT_SECONDS = 30;
export const REQUEST_TIMEOUT_MILLISECONDS = 30000;
export const ORDER_API_URL = 'https://orders.example.test';
export const DB_PASSWORD = 'not-a-real-secret';

class OrderPolicy {
  static readonly MAX_RETRY_ATTEMPTS = 3;
  readonly CACHE_TTL_SECONDS = 60;
}

class PaymentPolicy {
  static readonly MAX_RETRY_ATTEMPTS = 3;
}

function dispatch(order: string, retryLimit: number, requestTimeout: number): string {
  return order;
}

export function submit(order: string, requestTimeout: number): string {
  return dispatch(order, 3, requestTimeout);
}

export function submitWithTimeout(order: string, retryLimit: number): string {
  return dispatch(order, retryLimit, 30);
}

export function mutablePolicy(order: string): string {
  let retryLimit = 3;
  return dispatch(order, retryLimit, 60);
}

export function incidental(): number {
  let total = 0;
  for (let index = 0; index < 3; index += 1) total += index;
  return total;
}
