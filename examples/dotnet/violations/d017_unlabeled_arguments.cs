// acima-unit: orders
namespace Acima.Orders;

internal sealed class D017Request(string requestId, string customerId)
{
}

internal static class D017CallSites
{
    private static void CreateOrder(string requestId, string customerId, string customerName)
    {
    }

    public static void Run()
    {
        CreateOrder("r-1", "c-1", "Ada");
        _ = new D017Request("r-2", "c-2");
    }
}
