// acima-unit: catalog
using Microsoft.CodeAnalysis.CSharp;

namespace Acima.Catalog;

internal static class VendorSyntax
{
    public static CSharpSyntaxTree Parse(string text) => CSharpSyntaxTree.ParseText(text);
}
