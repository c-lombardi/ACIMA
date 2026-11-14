using System;

namespace Acima.Violations;

internal sealed class Order
{
}

internal sealed class ValueService
{
    public string Endpoint()
    {
        var ratesUrl = Environment.GetEnvironmentVariable("ORDERS_RATES_URL");
        var retryLimit = 3;
        return ratesUrl ?? string.Empty;
    }

    public int Send(Order order, int retryLimit) => retryLimit;

    public int Submit(Order order) => Send(order: order, retryLimit: 3);
}
