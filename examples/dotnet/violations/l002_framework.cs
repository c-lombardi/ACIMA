// acima-unit: orders.contracts
using Microsoft.AspNetCore.Mvc;

namespace Acima.Orders.Contracts;

/// <summary>A contract that speaks HTTP.</summary>
public sealed record Route(ControllerBase Controller);
