namespace Acima.Violations;

internal interface IRequestContext
{
}

internal sealed class RequestContext : IRequestContext
{
}

internal sealed class OrderValidator
{
    public bool Validate() => true;
}

internal sealed class PriceCache
{
    private readonly Dictionary<string, int> _prices = new();
}

internal sealed class OrdersService
{
    public OrdersService(IRequestContext context)
    {
        _ = context;
    }
}

internal sealed class InjectedService
{
    private readonly IRequestContext _context;

    public InjectedService(IRequestContext context)
    {
        _context = context;
    }

    public bool IsReady() => _context is not null;
}

internal sealed class LifecycleHost
{
    public void Configure(object services)
    {
        services.AddTransient<OrderValidator>();
        services.AddSingleton<PriceCache>();
        services.AddScoped<IRequestContext, RequestContext>();
        services.AddSingleton<OrdersService>();
        services.AddTransient<InjectedService>();
    }
}
