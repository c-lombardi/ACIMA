namespace Acme.Consumer;

public sealed class Consumer
{
    public object MakeWidget() => new Acme.Widgets.Widget();

    public object MakeNested() => new Acme.Widgets.Internal.Nested();
}
