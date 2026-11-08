// acima-unit: orders.contracts
using Acima.Catalog;

namespace Acima.Orders.Contracts;

/// <summary>A contract reaching into an implementation.</summary>
public sealed record Sneaky(CatalogModule Module);
