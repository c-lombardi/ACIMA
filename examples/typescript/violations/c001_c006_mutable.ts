// acima-unit: catalog.contracts
/** A contract nobody should be able to mutate. */
export interface CatalogDraft {
  readonly tags: string[];
  name: string;
  payload: any;
}
