/** Options accepted by every widget. */
export interface WidgetOptions {
  readonly id: string;
}

export const describe = (options: WidgetOptions): string => options.id;
