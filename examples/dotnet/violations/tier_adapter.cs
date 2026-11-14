// acima-unit: syntax.adapter
using Microsoft.CodeAnalysis.CSharp;

namespace Acima.Syntax;

internal sealed class SyntaxAdapter : ISyntaxPort
{
    public CSharpSyntaxTree Parse(string text) => CSharpSyntaxTree.ParseText(text);
}
