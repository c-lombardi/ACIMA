// acima-unit: catalog
using Acima.Orders;

namespace Acima.Catalog;

internal static class Mutate
{
    public static void Run() => Cart.Items = 1;
}
