using Acima.SharedKernel;

namespace Acima.Catalog.Contracts;

/// <summary>A purchasable product as other modules see it.</summary>
public sealed record ProductView(ProductId Id, string Name, Money Price);

/// <summary>The read capability Catalog promises.</summary>
public interface ICatalogReader
{
    /// <summary>Returns the product, or null when it does not exist.</summary>
    ProductView? Get(ProductId id);

    /// <summary>Returns every product, ordered by id.</summary>
    IReadOnlyList<ProductView> All();
}
