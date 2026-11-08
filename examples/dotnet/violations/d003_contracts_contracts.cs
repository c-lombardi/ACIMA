// acima-unit: orders.contracts
using Acima.Catalog.Contracts;

namespace Acima.Orders.Contracts;

/// <summary>A contract depending on another module's contract.</summary>
public sealed record Coupled(ProductView Product);
