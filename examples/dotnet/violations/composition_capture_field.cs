namespace Acima.Violations;

internal sealed partial class CapturingService
{
    internal static readonly IOrderRepository Repository = new SqlOrderRepository();
}
