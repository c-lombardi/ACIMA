// acima-unit: catalog
import { prisma } from 'zod';

export const load = async () => prisma.query('select 1');
