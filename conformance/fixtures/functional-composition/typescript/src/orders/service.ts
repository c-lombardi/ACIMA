// Compliant: currying with an explicit dependency parameter and pure HOFs are allowed.
export class Repository {
  save(request: unknown): unknown {
    return request;
  }
}

export const createOrder = (repository: Repository, request: unknown) =>
  repository.save(request);

export const curried = (repository: Repository) => (request: unknown) =>
  repository.save(request);

export const applyTwice = <T>(transform: (value: T) => T, value: T): T =>
  transform(transform(value));
