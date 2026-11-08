// acima-unit: orders.contracts
namespace Acima.Orders.Contracts;

/// <summary>A contract that decides what time it is.</summary>
public static class Clock
{
    public static DateTime Now() => DateTime.UtcNow;
}
