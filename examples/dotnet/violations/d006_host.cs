// acima-unit: catalog.contracts
using Acima.Host;

namespace Acima.Catalog.Contracts;

/// <summary>A contract that knows how it is hosted.</summary>
public sealed record HostBound(string Name);
