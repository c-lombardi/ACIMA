// Compliant component: its dependency is a required constructor parameter.
export class InMemoryRepository {}

export class OrdersService {
  constructor(private readonly repository: InMemoryRepository) {}
}
