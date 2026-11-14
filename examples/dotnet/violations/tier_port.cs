// acima-unit: syntax.port
using Microsoft.CodeAnalysis.CSharp;

namespace Acima.Syntax;

internal interface ISyntaxPort
{
    CSharpSyntaxTree Parse(string text);
}
