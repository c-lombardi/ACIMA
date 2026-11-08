import type { WidgetOptions } from 'acme-widgets';
import { createPool } from 'mysql2';

export const createDriver = (options: WidgetOptions) => ({ options, pool: createPool });
