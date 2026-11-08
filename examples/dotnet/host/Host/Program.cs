using CatalogContracts = Acima.Catalog.Contracts;
using CatalogModule = Acima.Catalog.CatalogModule;
using OrdersContracts = Acima.Orders.Contracts;
using OrdersModule = Acima.Orders.OrdersModule;
using PaymentsModule = Acima.Payments.PaymentsModule;

namespace Acima.Host;

internal static class Program
{
    private static void Main()
    {
        var catalog = new CatalogModule();
        var payments = new PaymentsModule(1000m);
        var orders = new OrdersModule(catalog.Reader, payments.Port);

        catalog.Add(new CatalogContracts.ProductView(
            new CatalogContracts.ProductId("p-1"),
            "Espresso beans",
            CatalogContracts.Money.Of(12.50m, CatalogContracts.Currency.Eur)));
        catalog.Add(new CatalogContracts.ProductView(
            new CatalogContracts.ProductId("p-2"),
            "Filter papers",
            CatalogContracts.Money.Of(3.20m, CatalogContracts.Currency.Eur)));

        var result = orders.Place(new OrdersContracts.PlaceOrder("c-1", new[]
        {
            new OrdersContracts.OrderLine(
                new OrdersContracts.ProductId("p-1"),
                OrdersContracts.Money.Of(12.50m, OrdersContracts.Currency.Eur),
                2),
            new OrdersContracts.OrderLine(
                new OrdersContracts.ProductId("p-2"),
                OrdersContracts.Money.Of(3.20m, OrdersContracts.Currency.Eur),
                1),
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
                OrdersContracts.OrderPlaced => "event: OrderPlaced",
                OrdersContracts.OrderRejected => "event: OrderRejected",
                _ => "event: unknown",
            });
        }
    }
}
