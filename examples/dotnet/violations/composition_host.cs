using System.Reflection;

namespace Acima.Violations;

internal static class CompositionHost
{
    public static void Build()
    {
        var types = Assembly.GetExecutingAssembly().GetTypes();
        _ = types;
    }
}
