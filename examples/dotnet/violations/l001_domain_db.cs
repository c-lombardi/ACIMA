// acima-unit: catalog
using Microsoft.EntityFrameworkCore;

namespace Acima.Catalog;

internal static class Loader
{
    public static int Run(DbContext context) => context.SaveChanges();
}
