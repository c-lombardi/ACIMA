// Compliant: required values arrive from the composition boundary.

export interface OrdersSettings {
  readonly retryLimit: number;
}

export class OrdersService {
  constructor(
    private readonly settings: OrdersSettings,
    private readonly endpoint: string,
  ) {}
}
