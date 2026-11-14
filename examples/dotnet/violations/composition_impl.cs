using System;

namespace Acima.Violations;

[AttributeUsage(AttributeTargets.Property | AttributeTargets.Field)]
internal sealed class InjectAttribute : Attribute
{
}

internal interface IOrderRepository
{
    string Save(string request);
}

internal sealed class SqlOrderRepository : IOrderRepository
{
    public string Save(string request) => request;
}

internal sealed class FieldInjectedService
{
    [Inject]
    public IOrderRepository Repository { get; private set; } = null!;
}

internal sealed partial class CapturingService
{
    public Func<string, string> Handler() => request => Repository.Save(request: request);
}

internal static class PartialHelpers
{
    public static Func<T, TResult> Partial<T, TDep, TResult>(
        Func<T, TDep, TResult> fn, TDep dependency) =>
        value => fn(value, dependency);
}

internal sealed class PartialService
{
    public Func<string, string> Handler() =>
        PartialHelpers.Partial<string, IOrderRepository, string>(
            fn: Save, dependency: CapturingService.Repository);

    private static string Save(string request, IOrderRepository repository) =>
        repository.Save(request: request);
}
