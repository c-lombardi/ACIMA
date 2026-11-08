// acima-unit: catalog
import { PrismaClient } from '@prisma/client';

export const load = async () => new PrismaClient().$queryRaw`select 1`;
