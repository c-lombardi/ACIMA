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
        var payments = new PaymentsModule(declineAbove: 1000m);
        var orders = new OrdersModule(catalog: catalog.Reader, payments: payments.Port);

        catalog.Add(product: new CatalogContracts.ProductView(
            Id: new CatalogContracts.ProductId(Value: "p-1"),
            Name: "Espresso beans",
            Price: CatalogContracts.Money.Of(amount: 12.50m, currency: CatalogContracts.Currency.Eur)));
        catalog.Add(product: new CatalogContracts.ProductView(
            Id: new CatalogContracts.ProductId(Value: "p-2"),
            Name: "Filter papers",
            Price: CatalogContracts.Money.Of(amount: 3.20m, currency: CatalogContracts.Currency.Eur)));

        var result = orders.Place(command: new OrdersContracts.PlaceOrder(CustomerId: "c-1", Lines: new[]
        {
            new OrdersContracts.OrderLine(
                ProductId: new OrdersContracts.ProductId(Value: "p-1"),
                UnitPrice: OrdersContracts.Money.Of(amount: 12.50m, currency: OrdersContracts.Currency.Eur),
                Quantity: 2),
            new OrdersContracts.OrderLine(
                ProductId: new OrdersContracts.ProductId(Value: "p-2"),
                UnitPrice: OrdersContracts.Money.Of(amount: 3.20m, currency: OrdersContracts.Currency.Eur),
                Quantity: 1),
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
