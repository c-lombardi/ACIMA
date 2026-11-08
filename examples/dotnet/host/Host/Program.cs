using Acima.Catalog;
using Acima.Catalog.Contracts;
using Acima.Orders;
using Acima.Orders.Contracts;
using Acima.Payments;
using Acima.SharedKernel;

namespace Acima.Host;

internal static class Program
{
    private static void Main()
    {
        var catalog = new CatalogModule();
        var payments = new PaymentsModule(1000m);
        var orders = new OrdersModule(catalog.Reader, payments.Port);

        catalog.Add(new ProductView(new ProductId("p-1"), "Espresso beans", Money.Of(12.50m, Currency.Eur)));
        catalog.Add(new ProductView(new ProductId("p-2"), "Filter papers", Money.Of(3.20m, Currency.Eur)));

        var result = orders.Place(new PlaceOrder("c-1", new[]
        {
            new OrderLine(new ProductId("p-1"), Money.Of(12.50m, Currency.Eur), 2),
            new OrderLine(new ProductId("p-2"), Money.Of(3.20m, Currency.Eur), 1),
        }));

        if (result.Rejected is not null)
        {
            Console.WriteLine($"rejected: {result.Rejected.Reason}");
            return;
        }

        Console.WriteLine($"placed: {result.Accepted!.Id} {result.Accepted.Total}");
        foreach (var published in orders.Published)
        {
            Console.WriteLine(published switch
            {
                OrderPlaced => "event: OrderPlaced",
                OrderRejected => "event: OrderRejected",
                _ => "event: unknown",
            });
        }
    }
}
