using Acima.Catalog.Contracts;

namespace Acima.Catalog;

internal sealed class ProductStore
{
    private readonly Dictionary<string, ProductView> _rows = new(StringComparer.Ordinal);

    public void Save(ProductView product) => _rows[product.Id.Value] = product;

    public ProductView? Find(ProductId id) => _rows.GetValueOrDefault(id.Value);

    public IReadOnlyList<ProductView> All() =>
        _rows.Values.OrderBy(product => product.Id.Value, StringComparer.Ordinal).ToArray();
}

internal sealed class CatalogReader(ProductStore store) : ICatalogReader
{
    public ProductView? Get(ProductId id) => store.Find(id: id);

    public IReadOnlyList<ProductView> All() => store.All();
}

/// <summary>Catalog's composition surface.</summary>
public sealed class CatalogModule
{
    private readonly ProductStore _store = new();
    private readonly ICatalogReader _reader;

    /// <summary>Creates the module with in-memory storage.</summary>
    public CatalogModule() => _reader = new CatalogReader(store: _store);

    /// <summary>The port other modules consume.</summary>
    public ICatalogReader Reader => _reader;

    /// <summary>Stores a product. Host-only.</summary>
    public void Add(ProductView product) => _store.Save(product: product);
}
