using System.Diagnostics;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml.Linq;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.Operations;

namespace Acima.ArchTests;

internal sealed class Unit
{
    public string Id { get; set; } = string.Empty;
    public string? Module { get; set; }
    public string Role { get; set; } = string.Empty;
    public List<string> Paths { get; set; } = new();
    public List<string> Namespaces { get; set; } = new();
}

internal sealed class Config
{
    public string Standard { get; set; } = "1.0.0";
    public string Language { get; set; } = "dotnet";
    public string Level { get; set; } = "L1";
    public List<Unit> Units { get; set; } = new();
    public List<string> Exclude { get; set; } = new();
    public string? Waivers { get; set; }
    public Profile? Profile { get; set; }
    public Dictionary<string, ExternalEntry>? Externals { get; set; }
    public List<string>? Manifests { get; set; }
    public List<string>? PartialHelpers { get; set; }
}

internal sealed class Profile
{
    public string? Kind { get; set; }
    public string? Owner { get; set; }
    public string? Justification { get; set; }
    public List<JsonElement>? PublicApi { get; set; }
    public List<AdapterEntry>? IntentionalAdapters { get; set; }
}

internal sealed class AdapterEntry
{
    public string? From { get; set; }
    public string? To { get; set; }
    public List<string>? Specifiers { get; set; }
    public List<string>? Paths { get; set; }
    public string? Owner { get; set; }
    public string? Reason { get; set; }
}

internal sealed class ExternalEntry
{
    public string? Tier { get; set; }
    public string? Owner { get; set; }
    public string? Reason { get; set; }
    public string? ReviewedOn { get; set; }
    public string? Expires { get; set; }
    public string? Adapter { get; set; }
    public string? Port { get; set; }
    public List<string>? Specifiers { get; set; }
    public List<string>? Types { get; set; }
}

internal sealed class Waiver
{
    public string? Rule { get; set; }
    public string? Scope { get; set; }
    public string? Owner { get; set; }
    public string? Reason { get; set; }
    public string? Expires { get; set; }
    public string? ReviewedOn { get; set; }
    public string? Fingerprint { get; set; }
}

internal sealed class WaiverDocument
{
    public List<Waiver> Waivers { get; set; } = new();
}

internal sealed record Finding(string Rule, string Severity, string Message, string Path, int Line, string Evidence, string Fingerprint, string? Classification = null);

internal sealed record Registration(string Service, string Implementation, string Lifetime, string Path, int Line, string Evidence);

internal sealed record Edge(string From, string To, string Path, int Line, string Evidence);

internal sealed record Classified(string Rule, string Path, int Line, string Evidence, string Classification, string DeclaredBy, string? Target, string Owner, string Reason);

internal sealed record PublicApiSurface(string Unit, List<string> Paths);

internal sealed class Enforcer
{
    private const string D001 = "ACIMA-D001";
    private const string D002 = "ACIMA-D002";
    private const string D003 = "ACIMA-D003";
    private const string D004 = "ACIMA-D004";
    private const string D005 = "ACIMA-D005";
    private const string D006 = "ACIMA-D006";
    private const string D007 = "ACIMA-D007";
    private const string D008 = "ACIMA-D008";
    private const string D009 = "ACIMA-D009";
    private const string L001 = "ACIMA-L001";
    private const string L002 = "ACIMA-L002";
    private const string L003 = "ACIMA-L003";
    private const string L004 = "ACIMA-L004";
    private const string C001 = "ACIMA-C001";
    private const string C002 = "ACIMA-C002";
    private const string C003 = "ACIMA-C003";
    private const string C004 = "ACIMA-C004";
    private const string C005 = "ACIMA-C005";
    private const string C006 = "ACIMA-C006";
    private const string C007 = "ACIMA-C007";
    private const string C008 = "ACIMA-C008";
    private const string A001 = "ACIMA-A001";
    private const string A002 = "ACIMA-A002";
    private const string A003 = "ACIMA-A003";
    private const string A004 = "ACIMA-A004";
    private const string G001 = "ACIMA-G001";
    private const string G002 = "ACIMA-G002";
    private const string G003 = "ACIMA-G003";
    private const string G004 = "ACIMA-G004";
    private const string G005 = "ACIMA-G005";
    private const string G006 = "ACIMA-G006";
    private const string D010 = "ACIMA-D010";
    private const string L005 = "ACIMA-L005";
    private const string L006 = "ACIMA-L006";
    private const string L007 = "ACIMA-L007";
    private const string D011 = "ACIMA-D011";
    private const string D012 = "ACIMA-D012";
    private const string A005 = "ACIMA-A005";
    private const string A006 = "ACIMA-A006";
    private const string D013 = "ACIMA-D013";
    private const string D014 = "ACIMA-D014";
    private const string D015 = "ACIMA-D015";
    private const string D016 = "ACIMA-D016";
    private const string D017 = "ACIMA-D017";
    private const string A007 = "ACIMA-A007";
    private const string A008 = "ACIMA-A008";
    private const string A009 = "ACIMA-A009";
    private const string A010 = "ACIMA-A010";
    private const string A011 = "ACIMA-A011";
    private const string A012 = "ACIMA-A012";
    private const string A013 = "ACIMA-A013";
    private const string A014 = "ACIMA-A014";
    private const string A015 = "ACIMA-A015";
    private const string N001 = "ACIMA-N001";
    private const string N002 = "ACIMA-N002";
    private const string N003 = "ACIMA-N003";

    private static readonly Dictionary<string, (string Severity, string Level)> Catalog = new(StringComparer.Ordinal)
    {
        [D001] = ("error", "L1"), [D002] = ("error", "L1"), [D003] = ("error", "L1"),
        [D004] = ("error", "L1"), [D005] = ("error", "L1"), [D006] = ("error", "L1"),
        [D007] = ("error", "L1"), [D008] = ("error", "L1"), [D009] = ("error", "L1"),
        [L001] = ("error", "L1"), [L002] = ("error", "L1"), [L003] = ("error", "L1"),
        [L004] = ("warning", "L1"),
        [C001] = ("error", "L2"), [C002] = ("error", "L2"), [C003] = ("error", "L2"),
        [C004] = ("error", "L2"), [C005] = ("error", "L2"), [C006] = ("error", "L2"),
        [C007] = ("warning", "L2"), [C008] = ("error", "L2"),
        [A001] = ("error", "L3"), [A002] = ("warning", "L3"),
        [A003] = ("error", "L3"), [A004] = ("warning", "L3"),
        [A005] = ("warning", "L3"), [A006] = ("warning", "L3"),
        [G001] = ("error", "L1"), [G002] = ("error", "L1"),
        [G003] = ("warning", "L2"), [G004] = ("error", "L2"),
        [G005] = ("error", "L1"),
        [D010] = ("error", "L1"),
        [L005] = ("warning", "L1"), [L006] = ("error", "L1"), [L007] = ("warning", "L1"),
        [G006] = ("warning", "L1"),
        [D011] = ("error", "L1"), [D012] = ("error", "L1"),
        [D013] = ("warning", "L1"), [D014] = ("warning", "L1"),
        [D015] = ("warning", "L1"), [D016] = ("warning", "L1"), [D017] = ("warning", "L1"),
        [A007] = ("warning", "L3"), [A008] = ("warning", "L3"), [A009] = ("warning", "L3"),
        [A010] = ("error", "L3"), [A011] = ("error", "L3"),
        [A012] = ("error", "L3"), [A013] = ("warning", "L3"),
        [A014] = ("error", "L3"), [A015] = ("error", "L3"),
        [N001] = ("warning", "L3"), [N002] = ("warning", "L3"), [N003] = ("warning", "L3"),
    };

    private static readonly Dictionary<string, string> NotExecuted = new(StringComparer.Ordinal)
    {
        [C003] = "behaviour versus validation is a semantic judgement",
        [C007] = "constructor completeness needs symbol and API analysis",
        [L004] = "service-locator APIs are framework-specific",
        [A002] = "configuration APIs differ per ecosystem",
        [A004] = "version-lock coupling is visible only across published packages",
        [G004] = "an API baseline needs a per-language surface format",
        [D010] = "third-party tier rules are implemented by the python and typescript enforcers in this revision",
        [L005] = "third-party tier rules are implemented by the python and typescript enforcers in this revision",
        [L006] = "third-party tier rules are implemented by the python and typescript enforcers in this revision",
        [L007] = "third-party tier rules are implemented by the python and typescript enforcers in this revision",
        [G006] = "manifest package governance is implemented by the python and typescript enforcers in this revision",
        [N003] = "semantic naming quality needs human review",
        [C008] = "business behavior visibility is a semantic contract review",
        [A010] = "effect ownership and commit boundaries require application and operational review",
        [A011] = "effect semantics require contract and API review",
        [A012] = "outcome truthfulness requires failure, retry and cancellation evidence",
        [A013] = "critical-effect evidence requires audit and telemetry inspection",
        [A014] = "whether telemetry observes or alters business behaviour needs review",
        [A015] = "consistency ownership and guarantees need design review",
    };

    private static readonly Dictionary<string, int> Rank = new() { ["L1"] = 1, ["L2"] = 2, ["L3"] = 3 };

    public static IReadOnlyDictionary<string, (string Severity, string Level)> CatalogRules => Catalog;
    public static IReadOnlyDictionary<string, string> NotExecutedRules => NotExecuted;
    public int SourceFiles => _files.Count;

    private static readonly Regex PropertySetter = new(@"\{[^{}]*\bset\s*;[^{}]*\}", RegexOptions.Compiled);
    private static readonly Regex PublicField = new(@"^\s*public\s+(?!static\b|const\b|readonly\b)[\w<>,\[\]\.\?]+\s+\w+\s*;", RegexOptions.Multiline | RegexOptions.Compiled);
    private static readonly Regex CollectionMember = new(@"\b(?:List|IList|ICollection|Dictionary|HashSet)\s*<|\b[A-Za-z_][A-Za-z0-9_.<>?]*\s*\[\s*\]", RegexOptions.Compiled);
    private static readonly Regex Ambient = new(@"\bDateTime(?:Offset)?\.(?:Now|UtcNow)\b|\bGuid\.NewGuid\s*\(|\bnew\s+Random\s*\(|\bEnvironment\.(?:MachineName|TickCount|GetEnvironmentVariable)|TimeProvider\.System", RegexOptions.Compiled);
    private static readonly Regex Persistence = new(@"\bDbContext\b|\bDbSet\s*<|\bIDbConnection\b|\bSqlConnection\b|\bNpgsql\w*\b|\bDapper\b|Microsoft\.EntityFrameworkCore", RegexOptions.Compiled);
    private static readonly Regex PersistenceNamespace = new(@"\b(?:Microsoft\.EntityFrameworkCore|System\.Data\.SqlClient|Microsoft\.Data\.Sqlite|Npgsql|Dapper)\b", RegexOptions.Compiled);
    private static readonly Regex Untyped = new(@"\bobject\??\s+\w+|\bdynamic\b", RegexOptions.Compiled);
    private static readonly Regex Framework = new(@"\bMicrosoft\.AspNetCore\b|\bMicrosoft\.EntityFrameworkCore\b|\bSystem\.Net\.Http\b|\bMicrosoft\.Extensions\.Configuration\b", RegexOptions.Compiled);
    private static readonly Regex UsingDirective = new(@"^\s*(?:global\s+)?using\s+(?:static\s+)?([\w\.]+)\s*;", RegexOptions.Multiline | RegexOptions.Compiled);
    private static readonly Regex NamespaceDeclaration = new(@"^\s*namespace\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*(?:;|\{)", RegexOptions.Multiline | RegexOptions.Compiled);
    private static readonly Regex PublicType = new(@"^\s*public\s+(?:sealed\s+|abstract\s+|readonly\s+|partial\s+|static\s+)*(?:class|record|struct|interface|enum)\s+(\w+)", RegexOptions.Multiline | RegexOptions.Compiled);
    private static readonly Regex InternalType = new(@"^\s*internal\s+(?:sealed\s+|abstract\s+|readonly\s+|partial\s+|static\s+)*(?:class|record|struct|interface)\s+(\w+)", RegexOptions.Multiline | RegexOptions.Compiled);
    private static readonly Regex InternalStatic = new(@"^\s*public\s+static\s+(?!readonly\b)[\w<>,\[\]\.\?]+\s+(\w+)\s*(?:=\s*(?!=)|;)", RegexOptions.Multiline | RegexOptions.Compiled);
    private static readonly Regex StringLiteral = new("\"((?:[^\"\\\\]|\\\\.)*)\"", RegexOptions.Compiled);
    private static readonly Regex SqlTable = new(@"(?i)\b(?:from|into|update|join)\s+([a-z][a-z0-9_]*)", RegexOptions.Compiled);
    private static readonly Regex WaiverFingerprint = new(@"^sha256:[0-9a-f]{64}$", RegexOptions.Compiled);

    private readonly string _root;
    private readonly Config _cfg;
    private readonly string _level;
    private readonly string _configName;
    private readonly List<Finding> _findings = new();
    private readonly Dictionary<string, string> _files = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Unit> _fileUnits = new(StringComparer.Ordinal);
    private readonly Dictionary<string, SyntaxNode> _syntax = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string[]> _sourceLines = new(StringComparer.Ordinal);
    private readonly List<string> _projects = new();
    private readonly List<Edge> _edges = new();
    private readonly Dictionary<string, Unit> _namespaceUnits = new(StringComparer.Ordinal);
    private readonly HashSet<string> _repositoryNamespaces = new(StringComparer.Ordinal);
    private readonly List<Classified> _classified = new();
    private readonly List<PublicApiSurface> _publicApi = new();
    private readonly List<MetadataReference> _metadataReferences = new();
    private readonly Dictionary<string, string> _packageByAssembly = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, CSharpCompilation> _compilations = new(StringComparer.Ordinal);
    private readonly Dictionary<string, SemanticModel> _semanticModels = new(StringComparer.Ordinal);
    private readonly Dictionary<string, List<BaseTypeDeclarationSyntax>> _types = new(StringComparer.Ordinal);
    private bool _semanticsBuilt;
    private bool _compilationsBuilt;
    private string? _packagingError;

    public IReadOnlyList<Classified> ClassifiedFindings => _classified;

    public Enforcer(string root, Config config, string level, string configName = "acima.config.json")
    {
        _root = Path.GetFullPath(root);
        _cfg = config;
        _level = Rank.ContainsKey(level) ? level : "L1";
        _configName = configName.Replace('\\', '/');
    }

    public IReadOnlyList<Finding> Run()
    {
        Collect();
        Classify();
        ParseSources();
        ValidateProfile();
        CheckProjects();
        CheckExternals();
        CheckUsings();
        CheckCycles();
        CheckTransitive();
        CheckVisibility();
        CheckContracts();
        CheckLayering();
        CheckSql();
        CheckStatics();
        CheckExplicitInputs();
        CheckNamedArguments();
        CheckComposition();
        CheckFunctionalCapture();
        CheckLifecycle();
        CheckNaming();
        CheckConfiguration();
        CheckOperationalValues();
        ApplyWaivers();
        return Dedupe();
    }

    private void Collect()
    {
        Walk(_root);
        foreach (var text in _files.Values)
        {
            foreach (Match match in NamespaceDeclaration.Matches(text))
            {
                _repositoryNamespaces.Add(match.Groups[1].Value);
            }
        }
        foreach (var project in _projects)
        {
            var unit = UnitForPath(project, string.Empty);
            if (unit is not null)
            {
                foreach (var ns in unit.Namespaces)
                {
                    _namespaceUnits[ns] = unit;
                }
            }
        }
    }

    private void Walk(string directory)
    {
        foreach (var entry in Directory.EnumerateFileSystemEntries(directory).OrderBy(e => e, StringComparer.Ordinal))
        {
            var name = Path.GetFileName(entry);
            if (name is "bin" or "obj" or ".git" or "node_modules") continue;

            var rel = Relative(entry);
            if (Directory.Exists(entry))
            {
                if (!Excluded(rel + "/")) Walk(entry);
                continue;
            }

            if (Excluded(rel)) continue;
            if (name.EndsWith(".cs", StringComparison.Ordinal))
            {
                _files[rel] = File.ReadAllText(entry);
            }
            else if (name.EndsWith(".csproj", StringComparison.Ordinal))
            {
                _projects.Add(rel);
            }
        }
    }

    private bool Excluded(string rel)
    {
        var trimmed = rel.TrimEnd('/');
        // The generated ACIMA workspace is not application source.
        if (trimmed.Equals("acima", StringComparison.OrdinalIgnoreCase)
            || trimmed.StartsWith("acima/", StringComparison.OrdinalIgnoreCase)) return true;
        foreach (var pattern in _cfg.Exclude)
        {
            var clean = pattern.Replace("**", string.Empty).Replace("*", string.Empty).TrimEnd('/');
            if (clean.Length == 0) continue;
            if (trimmed.Equals(clean, StringComparison.OrdinalIgnoreCase)) return true;
            if (trimmed.StartsWith(clean + "/", StringComparison.OrdinalIgnoreCase)) return true;
            if (trimmed.Split('/').Any(part => part.Equals(clean, StringComparison.OrdinalIgnoreCase))) return true;
        }

        return false;
    }

    private void Classify()
    {
        foreach (var path in _files.Keys.OrderBy(k => k, StringComparer.Ordinal).ToList())
        {
            var declared = UnitForPathByPrefix(path);
            var unit = UnitForPath(path, _files[path]);
            if (declared is not null && unit is not null && declared.Id != unit.Id)
            {
                Add(G005, $"Role override changes {path} from {declared.Id} to {unit.Id}.", path, 1, "acima-unit override");
            }
            if (unit is null)
            {
                Add(G005, $"Source file is not part of any declared unit: {path}", path, 1, string.Empty);
                _files.Remove(path);
                continue;
            }

            _fileUnits[path] = unit;
        }

        foreach (var unit in _cfg.Units)
        {
            foreach (var prefix in unit.Paths)
            {
                if (Excluded(prefix))
                {
                    Add(G005, $"Declared unit {unit.Id} excludes its own source: {prefix}.", prefix, 1, "exclude overrides unit mapping");
                }
            }
        }
    }

    private Unit? UnitForPathByPrefix(string path)
    {
        Unit? best = null;
        var bestLength = -1;
        foreach (var unit in _cfg.Units)
        {
            foreach (var prefix in unit.Paths)
            {
                var clean = prefix.TrimEnd('/');
                if ((path.Equals(clean, StringComparison.Ordinal) || path.StartsWith(clean + "/", StringComparison.Ordinal)) && clean.Length > bestLength)
                {
                    best = unit;
                    bestLength = clean.Length;
                }
            }
        }

        return best;
    }

    private Unit? UnitForPath(string path, string text)
    {
        if (text.Length > 0)
        {
            var head = text.Split('\n').Take(3);
            foreach (var line in head)
            {
                var marker = line.IndexOf("acima-unit:", StringComparison.Ordinal);
                if (marker < 0) continue;
                var token = line[(marker + "acima-unit:".Length)..].Trim().Split(' ', '\t')[0];
                var exact = _cfg.Units.FirstOrDefault(u => u.Id == token);
                if (exact is not null) return exact;
                var implementation = _cfg.Units.FirstOrDefault(u => u.Module == token && u.Role == "implementation");
                if (implementation is not null) return implementation;
                if (token.EndsWith(".contracts", StringComparison.Ordinal))
                {
                    var module = token[..^".contracts".Length];
                    var contracts = _cfg.Units.FirstOrDefault(u => u.Module == module && u.Role == "contracts");
                    if (contracts is not null) return contracts;
                }
            }
        }

        Unit? best = null;
        var bestLength = -1;
        foreach (var unit in _cfg.Units)
        {
            foreach (var prefix in unit.Paths)
            {
                var clean = prefix.TrimEnd('/');
                if ((path.Equals(clean, StringComparison.Ordinal) || path.StartsWith(clean + "/", StringComparison.Ordinal)) && clean.Length > bestLength)
                {
                    best = unit;
                    bestLength = clean.Length;
                }
            }
        }

        return best;
    }

    private void ValidateProfile()
    {
        var profile = _cfg.Profile;
        if (profile is null) return;
        const string configPath = "acima.config.json";
        var kind = profile.Kind ?? string.Empty;
        if (kind != "application" && kind != "library")
        {
            Add(G001, $"profile.kind is \"{profile.Kind}\"; expected \"application\" or \"library\".", configPath, 1, "profile.kind");
            return;
        }

        if (string.IsNullOrWhiteSpace(profile.Justification))
        {
            Add(G001, "profile has no justification; it would be an undocumented exemption.", configPath, 1, "profile.justification");
        }

        if (string.IsNullOrWhiteSpace(profile.Owner))
        {
            Add(G001, "profile has no owner; an exception without an owner is not reviewable.", configPath, 1, "profile.owner");
        }

        if (kind == "library" && !_projects.Any(IsPublishable))
        {
            var detail = _packagingError is null
                ? "library profile is not supported by the project files: no project evaluates as packable with a PackageId."
                : $"library profile could not evaluate package metadata: {_packagingError}";
            Add(G001, detail, configPath, 1, "profile.kind");
        }

        foreach (var element in profile.PublicApi ?? new List<JsonElement>())
        {
            if (element.ValueKind != JsonValueKind.Object)
            {
                Add(G001, "profile.publicApi entries must be objects with unit and paths; a bare unit is a blanket exemption.", configPath, 1, "profile.publicApi");
                continue;
            }

            var unit = element.TryGetProperty("unit", out var unitValue) ? unitValue.GetString() : null;
            var paths = element.TryGetProperty("paths", out var pathsValue) && pathsValue.ValueKind == JsonValueKind.Array
                ? pathsValue.EnumerateArray().Select(p => p.GetString())
                    .Where(p => !string.IsNullOrWhiteSpace(p)).Select(p => p!).ToList()
                : new List<string>();
            if (string.IsNullOrWhiteSpace(unit) || _cfg.Units.All(u => u.Id != unit))
            {
                Add(G001, $"profile.publicApi names the unknown unit {unit}.", configPath, 1, "profile.publicApi");
            }

            if (paths.Count == 0)
            {
                Add(G001, $"profile.publicApi for {unit} declares no paths; the whole unit would become public.", configPath, 1, "profile.publicApi");
            }
            else if (!string.IsNullOrWhiteSpace(unit))
            {
                _publicApi.Add(new PublicApiSurface(unit, paths));
            }
        }

        foreach (var adapter in profile.IntentionalAdapters ?? new List<AdapterEntry>())
        {
            var missing = new List<string>();
            if (string.IsNullOrWhiteSpace(adapter.From)) missing.Add("from");
            if (string.IsNullOrWhiteSpace(adapter.Owner)) missing.Add("owner");
            if (string.IsNullOrWhiteSpace(adapter.Reason)) missing.Add("reason");
            if (missing.Count > 0)
            {
                Add(G001, $"intentional adapter is missing: {string.Join(", ", missing)}.", configPath, 1, "profile.intentionalAdapters");
                continue;
            }

            if (_cfg.Units.All(u => u.Id != adapter.From))
            {
                Add(G001, $"intentional adapter names the unknown unit {adapter.From}.", configPath, 1, "profile.intentionalAdapters");
            }

            if (!string.IsNullOrWhiteSpace(adapter.To) && _cfg.Units.All(u => u.Id != adapter.To))
            {
                Add(G001, $"intentional adapter names the unknown target {adapter.To}.", configPath, 1, "profile.intentionalAdapters");
            }

            if (adapter.Paths is null || adapter.Paths.Count == 0)
            {
                Add(G001, $"intentional adapter {adapter.From} declares no paths; a whole-unit exemption can hide new edges.", configPath, 1, "profile.intentionalAdapters");
            }

            if (string.IsNullOrWhiteSpace(adapter.To) && (adapter.Specifiers is null || adapter.Specifiers.Count == 0))
            {
                Add(G001, $"intentional adapter {adapter.From} declares neither a target unit nor specifiers.", configPath, 1, "profile.intentionalAdapters");
            }
        }
    }

    private bool IsPublishable(string project)
    {
        var (packageId, isPackable, error) = EvaluatePackagingMetadata(project);
        if (error is not null)
        {
            _packagingError ??= $"{project}: {error}";
            return false;
        }

        return string.Equals(isPackable, "true", StringComparison.OrdinalIgnoreCase)
               && !string.IsNullOrWhiteSpace(packageId);
    }

    /// <summary>
    /// Evaluate PackageId and IsPackable instead of concatenating project XML.
    /// This deliberately lets MSBuild resolve SDK defaults and imports: PackageId
    /// may be inherited from Directory.Build.props, default to AssemblyName/project
    /// name, or be conditional, and IsPackable may be set in an imported file. This
    /// is evaluation only; it does not build or execute the target.
    /// </summary>
    private (string? PackageId, string? IsPackable, string? Error) EvaluatePackagingMetadata(string project)
    {
        var full = Path.Combine(_root, project);
        var start = new ProcessStartInfo("dotnet")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add("msbuild");
        start.ArgumentList.Add(full);
        start.ArgumentList.Add("-nologo");
        start.ArgumentList.Add("-getProperty:PackageId");
        start.ArgumentList.Add("-getProperty:IsPackable");

        try
        {
            using var process = Process.Start(start);
            if (process is null) return (null, null, "dotnet msbuild could not start");

            var stdout = process.StandardOutput.ReadToEndAsync();
            var stderr = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(30000))
            {
                process.Kill(entireProcessTree: true);
                return (null, null, "dotnet msbuild timed out");
            }

            var output = stdout.GetAwaiter().GetResult();
            var diagnostics = stderr.GetAwaiter().GetResult();
            if (process.ExitCode != 0)
            {
                var message = string.IsNullOrWhiteSpace(diagnostics) ? output : diagnostics;
                return (null, null, $"dotnet msbuild exited {process.ExitCode}: {message.Trim()}");
            }

            using var document = JsonDocument.Parse(output);
            if (!document.RootElement.TryGetProperty("Properties", out var properties))
                return (null, null, "dotnet msbuild returned no Properties");

            var packageId = properties.TryGetProperty("PackageId", out var packageValue)
                ? packageValue.GetString() : null;
            var isPackable = properties.TryGetProperty("IsPackable", out var packableValue)
                ? packableValue.GetString() : null;
            return (packageId, isPackable, null);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException or JsonException or System.ComponentModel.Win32Exception)
        {
            return (null, null, exception.Message);
        }
    }

    private static bool PathDeclared(List<string>? patterns, string path)
    {
        if (patterns is null) return false;
        foreach (var pattern in patterns)
        {
            if (GlobMatch(pattern, path)) return true;
            var literal = pattern.TrimEnd('*');
            if (literal.Length > 0 && path.StartsWith(literal, StringComparison.Ordinal)) return true;
        }

        return false;
    }

    private bool ClassifyAdapter(string rule, string path, int line, string evidence, Unit from, Unit? to,
        string? specifier, string separator = "/")
    {
        if (_cfg.Profile?.IntentionalAdapters is null) return false;
        foreach (var adapter in _cfg.Profile.IntentionalAdapters)
        {
            if (adapter.From != from.Id) continue;
            if (!PathDeclared(adapter.Paths, path)) continue;
            if (to is not null && (string.IsNullOrWhiteSpace(adapter.To) || adapter.To != to.Id)) continue;
            if (!string.IsNullOrWhiteSpace(specifier))
            {
                var specs = adapter.Specifiers ?? new List<string>();
                if (!specs.Any(candidate => specifier == candidate
                        || specifier.StartsWith(candidate + separator, StringComparison.Ordinal))) continue;
            }

            if (string.IsNullOrWhiteSpace(adapter.To) && (adapter.Specifiers is null || adapter.Specifiers.Count == 0)) continue;
            _classified.Add(new Classified(rule, path, Math.Max(line, 1),
                evidence.Length > 200 ? evidence[..200] : evidence, "intentional-adapter", adapter.From!,
                adapter.To, adapter.Owner ?? string.Empty, adapter.Reason ?? string.Empty));
            return true;
        }

        return false;
    }

    private bool ClassifyPublicApi(string rule, string path, int line, string evidence, Unit unit)
    {
        var surface = _publicApi.FirstOrDefault(candidate => candidate.Unit == unit.Id
            && PathDeclared(candidate.Paths, path));
        if (surface is null) return false;
        _classified.Add(new Classified(rule, path, Math.Max(line, 1),
            evidence.Length > 200 ? evidence[..200] : evidence, "declared-public-api", surface.Unit,
            null, _cfg.Profile?.Owner ?? string.Empty, _cfg.Profile?.Justification ?? string.Empty));
        return true;
    }

    private void CheckProjects()
    {
        foreach (var project in _projects)
        {
            var unit = UnitForPath(project, string.Empty);
            if (unit is null) continue;

            var full = Path.Combine(_root, project);
            var text = File.ReadAllText(full);
            XDocument document;
            try
            {
                document = XDocument.Parse(text);
            }
            catch (Exception)
            {
                Add(G005, $"Project file is not valid XML: {project}", project, 1, string.Empty);
                continue;
            }

            foreach (var element in document.Descendants().Where(e => e.Name.LocalName == "ProjectReference"))
            {
                var include = element.Attribute("Include")?.Value;
                if (string.IsNullOrWhiteSpace(include)) continue;

                // Analyzer and source-generator references do not produce runtime assembly
                // dependencies. Treating them as runtime edges creates false D005/D008 cycles.
                var referenceOutput = element.Attribute("ReferenceOutputAssembly")?.Value;
                var outputItem = element.Attribute("OutputItemType")?.Value;
                if (string.Equals(referenceOutput, "false", StringComparison.OrdinalIgnoreCase) ||
                    (outputItem?.Contains("Analyzer", StringComparison.OrdinalIgnoreCase) ?? false) ||
                    (outputItem?.Contains("SourceGenerator", StringComparison.OrdinalIgnoreCase) ?? false))
                {
                    continue;
                }

                var baseDirectory = Path.GetDirectoryName(full)!;
                var targetFull = Path.GetFullPath(Path.Combine(baseDirectory, include.Replace('\\', Path.DirectorySeparatorChar)));
                var targetPath = Relative(targetFull);
                var target = UnitForPath(targetPath, string.Empty);
                var line = LineOf(text, include);
                if (target is null) continue;

                _edges.Add(new Edge(unit.Id, target.Id, project, line, include));
                CheckEdge(unit, target, project, line, include);
            }

            foreach (var element in document.Descendants().Where(e => e.Name.LocalName == "PackageReference"))
            {
                var include = element.Attribute("Include")?.Value;
                if (string.IsNullOrWhiteSpace(include)) continue;
                var line = LineOf(text, include);
                if (unit.Role == "contracts")
                {
                    Add(D004, $"contracts project {unit.Id} has a PackageReference: {include}", project, line, include);
                }
                else if (unit.Role == "shared-kernel")
                {
                    Add(D007, $"shared kernel project has a PackageReference: {include}", project, line, include);
                }

                var packageTarget = UnitForPackage(include);
                if (packageTarget is not null && packageTarget.Id != unit.Id)
                {
                    _edges.Add(new Edge(unit.Id, packageTarget.Id, project, line, include));
                    CheckEdge(unit, packageTarget, project, line, include);
                }
            }
        }
    }

    private Unit? UnitForPackage(string package)
    {
        // Match the package identity, not a substring of it. A module named "tools" must not
        // claim the third-party package "Grpc.Tools": that produced a phantom
        // contracts -> implementation edge (D002) plus transitive D008 findings in a real
        // 27-project solution. An in-repo package belongs to a module only when its id starts
        // with that module id at a dot boundary.
        var wantsContracts = package.Contains("contracts", StringComparison.OrdinalIgnoreCase);
        foreach (var unit in _cfg.Units)
        {
            if (string.IsNullOrWhiteSpace(unit.Module)) continue;
            var module = unit.Module.Trim();
            if (!package.StartsWith(module + ".", StringComparison.OrdinalIgnoreCase)) continue;
            if (wantsContracts && unit.Role == "contracts") return unit;
            if (!wantsContracts && unit.Role == "implementation") return unit;
        }

        return null;
    }

    private void ParseSources()
    {
        foreach (var (path, text) in _files)
        {
            var tree = CSharpSyntaxTree.ParseText(text,
                new CSharpParseOptions(LanguageVersion.Latest), path);
            _syntax[path] = tree.GetRoot();
            _sourceLines[path] = text.Split(new[] { "\r\n", "\n" }, StringSplitOptions.None);
        }

        foreach (var (path, syntax) in _syntax)
        {
            foreach (var type in syntax.DescendantNodes().OfType<BaseTypeDeclarationSyntax>())
            {
                var name = type.Identifier.ValueText;
                if (!_types.TryGetValue(name, out var entries))
                    _types[name] = entries = new List<BaseTypeDeclarationSyntax>();
                entries.Add(type);
            }
        }
    }

    private void CheckUsings()
    {
        // Roslyn supplies the directive node, its name and its exact source location. The
        // previous regex pass could not distinguish a directive from a comment or a string.
        foreach (var (path, syntax) in _syntax.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var from = _fileUnits[path];
            foreach (var directive in syntax.DescendantNodes().OfType<UsingDirectiveSyntax>())
            {
                if (directive.Alias is not null || directive.Name is null) continue;
                var ns = directive.Name.ToString();
                if (string.IsNullOrWhiteSpace(ns) || ns.Contains("::", StringComparison.Ordinal)) continue;
                var line = directive.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
                var evidence = directive.ToString().Trim();
                var target = ResolveNamespace(ns);

                if (target is not null)
                {
                    if (target.Id == from.Id) continue;
                    _edges.Add(new Edge(from.Id, target.Id, path, line, evidence));
                    CheckEdge(from, target, path, line, evidence);
                    continue;
                }

                if (ns.StartsWith("Acima.", StringComparison.Ordinal)) continue;
                if (ns.StartsWith("System", StringComparison.Ordinal)) continue;
                if (IsRepositoryNamespace(ns)) continue;

                if (from.Role == "contracts")
                {
                    Add(D004, $"contracts unit {from.Id} depends on third-party namespace: {ns}", path, line, evidence);
                }
                else if (from.Role == "shared-kernel")
                {
                    Add(D007, $"shared kernel depends on a third-party namespace: {ns}", path, line, evidence);
                }
            }
        }
    }

    private static readonly HashSet<string> ExplicitInputRoles = new(StringComparer.Ordinal)
    {
        "implementation", "host", "adapter", "port",
    };

    private static readonly HashSet<string> CompositionRoles = new(StringComparer.Ordinal)
    {
        "implementation", "host", "adapter",
    };

    private static readonly HashSet<string> FunctionalRoles = new(StringComparer.Ordinal)
    {
        "implementation", "adapter",
    };

    private static readonly HashSet<string> NamingRoles = new(StringComparer.Ordinal)
    {
        "contracts", "implementation", "adapter", "host", "port", "shared-kernel",
    };

    private static readonly HashSet<string> ConfigReadRoles = new(StringComparer.Ordinal)
    {
        "implementation", "adapter",
    };

    private static readonly HashSet<string> ValueRoles = new(StringComparer.Ordinal)
    {
        "implementation", "adapter", "host",
    };

    private static readonly HashSet<string> DiscoveryMethods = new(StringComparer.Ordinal)
    {
        "GetTypes", "GetExportedTypes", "GetAssemblies", "Scan", "FromAssemblyOf",
        "FromAssemblies", "AddClasses", "RegisterAssemblyTypes",
    };

    private static readonly HashSet<string> InjectionAttributes = new(StringComparer.Ordinal)
    {
        "Inject", "Autowired", "Dependency", "FromServices", "FromKeyedServices",
    };

    private static readonly HashSet<string> FunctionalTokens = new(StringComparer.Ordinal)
    {
        "repository", "repositories", "repo", "service", "services", "client", "clients",
        "gateway", "gateways", "adapter", "adapters", "logger", "logging", "config",
        "configuration", "settings", "store", "stores", "database", "db", "connection",
        "connections", "session", "provider", "providers", "bus", "queue", "publisher",
        "producer", "consumer", "auth", "authorization", "security", "clock", "cache",
        "registry", "locator", "container", "resource", "resources",
    };

    private static readonly HashSet<string> OperationalTokens = new(StringComparer.Ordinal)
    {
        "timeout", "timeouts", "retry", "retries", "limit", "limits", "threshold",
        "thresholds", "ttl", "interval", "intervals", "batch", "rate", "rates",
        "retention", "capacity", "delay", "quota", "backoff", "concurrency", "attempts",
        "workers", "pagesize", "endpoint", "endpoints", "url", "urls", "uri", "host",
        "hostname", "port", "queue", "topic", "bucket", "minimum", "minimums", "maximum",
        "maximums", "duration", "durations", "expiry", "expiration", "deadline", "window",
        "windows", "grace", "heartbeat", "poll", "discount", "tax", "fee", "fees",
        "eligibility", "nonce", "salt", "signature", "secret", "secrets", "password",
        "passwords", "credential", "credentials",
    };

    private static readonly HashSet<string> ConfigurationTokens = new(StringComparer.Ordinal)
    {
        "endpoint", "endpoints", "url", "urls", "uri", "host", "hostname", "port",
        "queue", "topic", "bucket", "region", "environment", "deployment",
    };

    private static readonly HashSet<string> SecretTokens = new(StringComparer.Ordinal)
    {
        "nonce", "salt", "signature", "secret", "secrets", "password", "passwords",
        "credential", "credentials",
    };

    private static readonly HashSet<string> GenericTypeNames = new(StringComparer.Ordinal)
    {
        "Helper", "Manager", "Handler", "Processor", "Utility", "Service", "Provider",
        "Factory", "Common", "Base", "Default", "Generic",
    };

    private static readonly string[] GenericTypeSuffixes =
    {
        "Helper", "Manager", "Processor", "Utility", "Common", "Default", "Generic",
    };

    private static readonly HashSet<string> MutableContainerNames = new(StringComparer.Ordinal)
    {
        "List", "Dictionary", "HashSet", "SortedSet", "SortedDictionary", "Collection",
        "ObservableCollection", "ConcurrentDictionary", "ConcurrentBag", "ConcurrentQueue",
        "ConcurrentStack", "BlockingCollection",
    };

    private void CheckExplicitInputs()
    {
        foreach (var (path, syntax) in _syntax.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (!ExplicitInputRoles.Contains(unit.Role)) continue;
            var lines = _files[path].Split(new[] { "\r\n", "\n" }, StringSplitOptions.None);

            foreach (var constructor in syntax.DescendantNodes().OfType<ConstructorDeclarationSyntax>())
            {
                CheckOptionalParameters(D011, unit, path, lines, constructor.ParameterList,
                    "{0} constructs with the optional input {1}; a dependency the component needs must be required at construction.");
            }

            foreach (var declaration in syntax.DescendantNodes().OfType<TypeDeclarationSyntax>())
            {
                var parameters = declaration switch
                {
                    ClassDeclarationSyntax type => type.ParameterList,
                    RecordDeclarationSyntax record => record.ParameterList,
                    StructDeclarationSyntax structure => structure.ParameterList,
                    _ => null,
                };
                if (parameters is not null)
                {
                    CheckOptionalParameters(D011, unit, path, lines, parameters,
                        "{0} constructs with the optional input {1}; a dependency the component needs must be required at construction.");
                }
            }

            foreach (var method in syntax.DescendantNodes().OfType<MethodDeclarationSyntax>())
            {
                if (method.Modifiers.Any(token => token.IsKind(SyntaxKind.OverrideKeyword)
                        || token.IsKind(SyntaxKind.AbstractKeyword)
                        || token.IsKind(SyntaxKind.ExternKeyword))) continue;
                if (method.Body is null && method.ExpressionBody is null) continue;
                CheckOptionalParameters(D012, unit, path, lines, method.ParameterList,
                    "{0} lets a caller omit {1} in " + method.Identifier.ValueText +
                    "(); if that omission changes behaviour, require the decision at the call site.");
            }

            foreach (var local in syntax.DescendantNodes().OfType<LocalFunctionStatementSyntax>())
            {
                if (local.Body is null && local.ExpressionBody is null) continue;
                CheckOptionalParameters(D012, unit, path, lines, local.ParameterList,
                    "{0} lets a caller omit {1} in " + local.Identifier.ValueText +
                    "(); if that omission changes behaviour, require the decision at the call site.");
            }
        }
    }

    private void CheckOptionalParameters(string rule, Unit unit, string path, string[] sourceLines,
        ParameterListSyntax parameters, string messageFormat)
    {
        foreach (var parameter in parameters.Parameters)
        {
            if (parameter.Default is null) continue;
            var name = parameter.Identifier.ValueText;
            if (string.IsNullOrEmpty(name)) continue;
            var line = parameter.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
            var evidence = line > 0 && line <= sourceLines.Length
                ? sourceLines[line - 1].Trim()
                : parameter.ToString();
            Add(rule, string.Format(CultureInfo.InvariantCulture, messageFormat, unit.Id, name), path, line, evidence);
        }
    }

    private static readonly string[] TierRules =
    {
        L005, L006, L007, D010, G006,
    };

    private static readonly string[] ExternalFields =
    {
        "tier", "owner", "reason", "reviewedOn", "expires",
    };

    private static readonly string[] ExternalTiers =
    {
        "platform", "integration", "utility",
    };

    public static IReadOnlyDictionary<string, string> NotExecutedFor(Config? config)
    {
        var result = new Dictionary<string, string>(NotExecuted, StringComparer.Ordinal);
        if (config?.Externals is not null)
        {
            foreach (var rule in TierRules) result.Remove(rule);
        }

        if (config?.Externals is null)
        {
            foreach (var rule in TierRules)
                result[rule] = "externals map not declared in acima.config.json";
        }

        if (config?.PartialHelpers is null)
            result[D016] = "partial helper allowlist not declared in acima.config.json";
        else
            result.Remove(D016);
        return result;
    }

    private void CheckExternals()
    {
        if (_cfg.Externals is null) return;
        EnsureSemantics();

        var configPath = Path.IsPathRooted(_configName)
            ? Relative(_configName)
            : _configName;
        var configFile = Path.IsPathRooted(_configName) ? _configName : Path.Combine(_root, _configName);
        var configText = File.Exists(configFile) ? File.ReadAllText(configFile) : string.Empty;
        int EntryLine(string name) => configText.Length == 0 ? 1 : LineOf(configText, $"\"{name}\"");

        var adapterUnits = _cfg.Units.Where(unit => unit.Role == "adapter")
            .ToDictionary(unit => unit.Id, StringComparer.Ordinal);
        var portUnits = _cfg.Units.Where(unit => unit.Role == "port")
            .ToDictionary(unit => unit.Id, StringComparer.Ordinal);
        var declaredAdapters = new HashSet<string>(StringComparer.Ordinal);

        foreach (var (name, raw) in _cfg.Externals)
        {
            var entry = raw ?? new ExternalEntry();
            var missing = ExternalFields
                .Where(field => string.IsNullOrWhiteSpace(Field(entry, field)))
                .ToList();
            if (missing.Count > 0)
            {
                Add(G001, $"externals entry {name} is missing: {string.Join(", ", missing)}.",
                    configPath, EntryLine(name), name);
                continue;
            }

            var tier = (entry.Tier ?? string.Empty).Trim();
            if (!ExternalTiers.Contains(tier, StringComparer.Ordinal))
            {
                Add(G001, $"externals entry {name} has unknown tier {tier}; expected " +
                    $"{string.Join(", ", ExternalTiers)}.", configPath, EntryLine(name), name);
                continue;
            }

            if (tier != "integration") continue;
            var adapter = (entry.Adapter ?? string.Empty).Trim();
            var port = (entry.Port ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(adapter) || string.IsNullOrWhiteSpace(port))
            {
                var gap = string.IsNullOrWhiteSpace(adapter) ? "adapter" : "port";
                Add(L006, $"integration entry {name} declares no {gap}; an adapter without a port " +
                    "is an unguarded vendor import.", configPath, EntryLine(name), name);
                continue;
            }

            if (!adapterUnits.ContainsKey(adapter))
            {
                Add(G001, $"externals entry {name} names adapter {adapter}, which is not a " +
                    "declared adapter unit.", configPath, EntryLine(name), name);
                continue;
            }

            if (!portUnits.ContainsKey(port))
            {
                Add(G001, $"externals entry {name} names port {port}, which is not a declared " +
                    "port unit.", configPath, EntryLine(name), name);
                continue;
            }

            declaredAdapters.Add(adapter);
        }

        foreach (var unitId in adapterUnits.Keys.OrderBy(value => value, StringComparer.Ordinal))
        {
            if (declaredAdapters.Contains(unitId)) continue;
            var first = _fileUnits
                .Where(pair => pair.Value.Id == unitId)
                .Select(pair => pair.Key)
                .OrderBy(value => value, StringComparer.Ordinal)
                .FirstOrDefault();
            Add(L006, $"adapter unit {unitId} is declared in no externals entry; it has no port " +
                "and no reviewed vendor.", first ?? configPath, 1, unitId);
        }

        var claimed = new HashSet<(string Path, int Line)>();
        foreach (var (path, syntax) in _syntax.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (unit.Role is "tooling" or "test") continue;
            var sourceLines = _files[path].Split(new[] { "\r\n", "\n" }, StringSplitOptions.None);
            var model = SemanticModelFor(path);

            foreach (var directive in syntax.DescendantNodes().OfType<UsingDirectiveSyntax>())
            {
                if (directive.Name is null) continue;
                var found = ExternalForUsing(directive, model);
                if (found is null) continue;
                var (name, entry) = found.Value;
                var tier = (entry.Tier ?? string.Empty).Trim();
                var line = directive.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
                var evidence = directive.ToString().Trim();
                if (unit.Role == "port")
                {
                    Add(D010, $"port unit {unit.Id} imports the third-party package {name}; a " +
                        "port declares the capability, never the vendor.", path, line, evidence);
                    continue;
                }

                if (tier != "integration" || unit.Role == "adapter") continue;
                claimed.Add((path, line));
                Add(L005, $"{unit.Id} imports the integration library {name}; only its adapter " +
                    $"({(entry.Adapter ?? "undeclared")}) may import it, everyone else takes the port.",
                    path, line, evidence);
            }

            foreach (var typeSyntax in syntax.DescendantNodes().OfType<TypeSyntax>())
            {
                if (typeSyntax is PredefinedTypeSyntax) continue;
                if (typeSyntax is IdentifierNameSyntax identifier && identifier.Identifier.ValueText == "var") continue;
                var found = ExternalForType(typeSyntax, model);
                if (found is null) continue;
                var (name, entry) = found.Value;
                var line = typeSyntax.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
                if (!claimed.Add((path, line))) continue;
                var tier = (entry.Tier ?? string.Empty).Trim();
                var typeName = TypeLeaf(typeSyntax);
                if (string.IsNullOrEmpty(typeName)) typeName = typeSyntax.ToString();
                var evidence = line > 0 && line <= sourceLines.Length
                    ? sourceLines[line - 1].Trim()
                    : typeName;

                if (unit.Role == "port")
                {
                    Add(D010, $"port unit {unit.Id} names the vendor type {typeName} from {name}.",
                        path, line, evidence);
                    continue;
                }

                if (unit.Role == "adapter") continue;
                if (tier == "utility" && unit.Role != "contracts") continue;
                Add(L007, $"{unit.Id} names the vendor type {typeName} from {name} outside its adapter.",
                    path, line, evidence);
            }
        }

        var declaredPackages = new HashSet<string>(
            _cfg.Externals.Keys.Select(NormalizePackage), StringComparer.Ordinal);
        foreach (var (path, line, package) in ManifestPackages())
        {
            if (declaredPackages.Contains(NormalizePackage(package))) continue;
            Add(G006, $"manifest dependency {package} has no externals entry: declare its tier, " +
                "owner and review date.", path, line, package);
        }

        var today = DateOnly.FromDateTime(DateTime.UtcNow);
        foreach (var (name, raw) in _cfg.Externals)
        {
            var expires = (raw?.Expires ?? string.Empty).Trim();
            if (expires.Length == 0) continue;
            if (!DateOnly.TryParseExact(expires, "yyyy-MM-dd", CultureInfo.InvariantCulture,
                    DateTimeStyles.None, out var expiry))
            {
                Add(G001, $"externals entry {name} has a non-ISO expiry: {expires}.",
                    configPath, EntryLine(name), name);
            }
            else if (expiry < today)
            {
                Add(G006, $"externals entry {name} passed its review date on {expires}; renew or " +
                    "remove the dependency.", configPath, EntryLine(name), name);
            }
        }
    }

    private static string Field(ExternalEntry entry, string field) => field switch
    {
        "tier" => entry.Tier ?? string.Empty,
        "owner" => entry.Owner ?? string.Empty,
        "reason" => entry.Reason ?? string.Empty,
        "reviewedOn" => entry.ReviewedOn ?? string.Empty,
        "expires" => entry.Expires ?? string.Empty,
        _ => string.Empty,
    };

    private static string NormalizePackage(string value) => value.Replace('-', '_').ToLowerInvariant();

    private (string Name, ExternalEntry Entry)? FindExternalByPackage(string package)
    {
        if (_cfg.Externals is null) return null;
        var normalized = NormalizePackage(package);
        foreach (var (name, raw) in _cfg.Externals)
        {
            if (NormalizePackage(name) == normalized) return (name, raw ?? new ExternalEntry());
            var entry = raw ?? new ExternalEntry();
            foreach (var specifier in entry.Specifiers ?? new List<string>())
            {
                if (NormalizePackage(specifier) == normalized) return (name, entry);
            }
        }

        return null;
    }

    private (string Name, ExternalEntry Entry)? FindExternalBySpecifier(string specifier)
    {
        if (_cfg.Externals is null) return null;
        var normalized = NormalizePackage(specifier);
        (string Name, ExternalEntry Entry)? best = null;
        foreach (var (name, raw) in _cfg.Externals)
        {
            var entry = raw ?? new ExternalEntry();
            var known = new[] { name }.Concat(entry.Specifiers ?? new List<string>());
            foreach (var candidate in known)
            {
                var key = NormalizePackage(candidate);
                if (key.Length == 0) continue;
                if (!(normalized == key || normalized.StartsWith(key + ".", StringComparison.Ordinal)))
                    continue;
                if (best is null || key.Length > NormalizePackage(best.Value.Name).Length)
                    best = (name, entry);
            }
        }

        return best;
    }

    private (string Name, ExternalEntry Entry)? ExternalForUsing(UsingDirectiveSyntax directive,
        SemanticModel model)
    {
        var symbol = model.GetSymbolInfo(directive.Name!).Symbol;
        var assembly = AssemblyOf(symbol);
        if (assembly is not null)
        {
            var package = PackageForAssembly(assembly);
            if (package is not null)
            {
                var found = FindExternalByPackage(package);
                if (found is not null) return found;
            }
        }

        return FindExternalBySpecifier(directive.Name!.ToString());
    }

    private (string Name, ExternalEntry Entry)? ExternalForType(TypeSyntax syntax, SemanticModel model)
    {
        var type = model.GetTypeInfo(syntax).Type;
        var assembly = AssemblyOf(type);
        if (assembly is not null)
        {
            var package = PackageForAssembly(assembly);
            if (package is not null)
            {
                var found = FindExternalByPackage(package);
                if (found is not null) return found;
            }
        }

        var leaf = TypeLeaf(syntax);
        if (string.IsNullOrEmpty(leaf) || _cfg.Externals is null) return null;
        foreach (var (name, raw) in _cfg.Externals)
        {
            var entry = raw ?? new ExternalEntry();
            if ((entry.Types ?? new List<string>()).Contains(leaf, StringComparer.Ordinal))
                return (name, entry);
        }

        return null;
    }

    private static string? AssemblyOf(ISymbol? symbol)
    {
        return symbol switch
        {
            IAliasSymbol alias => AssemblyOf(alias.Target),
            INamespaceSymbol ns => ns.ConstituentNamespaces
                .Select(candidate => candidate.ContainingAssembly?.Name)
                .FirstOrDefault(value => !string.IsNullOrEmpty(value)) ?? ns.ContainingAssembly?.Name,
            ITypeSymbol type => type.ContainingAssembly?.Name,
            _ => symbol?.ContainingAssembly?.Name,
        };
    }

    private string? PackageForAssembly(string assembly)
    {
        if (_packageByAssembly.TryGetValue(assembly, out var package)) return package;
        return null;
    }

    private SemanticModel SemanticModelFor(string path)
    {
        EnsureCompilations();
        if (_semanticModels.TryGetValue(path, out var model)) return model;
        var tree = _syntax[path].SyntaxTree;
        var compilation = CSharpCompilation.Create(
            "AcimaSemantic_" + Guid.NewGuid().ToString("N"),
            new[] { tree }, _metadataReferences,
            new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
        return compilation.GetSemanticModel(tree);
    }

    private void EnsureCompilations()
    {
        if (_compilationsBuilt) return;
        _compilationsBuilt = true;
        EnsureSemantics();

        var trees = _syntax.ToDictionary(pair => pair.Key, pair => pair.Value.SyntaxTree,
            StringComparer.Ordinal);
        var assigned = new HashSet<string>(StringComparer.Ordinal);
        foreach (var project in _projects.OrderBy(path => path, StringComparer.Ordinal))
        {
            var closure = new HashSet<string>(StringComparer.Ordinal);
            AddProjectClosure(project, closure);
            var projectTrees = closure
                .Where(path => trees.ContainsKey(path))
                .OrderBy(path => path, StringComparer.Ordinal)
                .Select(path => trees[path])
                .ToList();
            foreach (var path in closure) assigned.Add(path);
            if (projectTrees.Count == 0) continue;
            _compilations[project] = CSharpCompilation.Create(
                "AcimaProject_" + StableHash(project), projectTrees, _metadataReferences,
                new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
        }

        var unassigned = trees.Keys.Where(path => !assigned.Contains(path))
            .OrderBy(path => path, StringComparer.Ordinal).ToList();
        if (unassigned.Count > 0)
        {
            _compilations[string.Empty] = CSharpCompilation.Create(
                "AcimaLooseSources",
                unassigned.Select(path => trees[path]).ToList(), _metadataReferences,
                new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
        }

        foreach (var (path, tree) in trees)
        {
            var project = ProjectForPath(path);
            var compilation = project is not null && _compilations.TryGetValue(project, out var projectCompilation)
                ? projectCompilation
                : _compilations.TryGetValue(string.Empty, out var looseCompilation)
                    ? looseCompilation
                    : null;
            if (compilation is not null)
                _semanticModels[path] = compilation.GetSemanticModel(tree);
        }
    }

    private string? ProjectForPath(string path)
    {
        string? best = null;
        var bestLength = -1;
        foreach (var project in _projects)
        {
            var directory = Path.GetDirectoryName(project)?.Replace('\\', '/') ?? string.Empty;
            if (directory == ".") directory = string.Empty;
            if (directory.Length > 0
                && !(path.Equals(directory, StringComparison.Ordinal)
                    || path.StartsWith(directory + "/", StringComparison.Ordinal))) continue;
            if (directory.Length <= bestLength) continue;
            best = project;
            bestLength = directory.Length;
        }

        return best;
    }

    private void AddProjectClosure(string project, HashSet<string> paths)
    {
        if (!paths.Add(project)) return;
        var full = Path.Combine(_root, project);
        var directory = Path.GetDirectoryName(full);
        if (directory is null) return;
        foreach (var path in _files.Keys.OrderBy(value => value, StringComparer.Ordinal))
        {
            var candidate = Path.Combine(_root, path);
            if (candidate.StartsWith(directory + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
                || candidate.Equals(directory, StringComparison.OrdinalIgnoreCase))
                paths.Add(path);
        }

        if (!File.Exists(full)) return;
        XDocument document;
        try
        {
            document = XDocument.Parse(File.ReadAllText(full));
        }
        catch (Exception error) when (error is IOException or System.Xml.XmlException)
        {
            return;
        }

        foreach (var reference in document.Descendants().Where(item => item.Name.LocalName == "ProjectReference"))
        {
            var include = reference.Attribute("Include")?.Value;
            if (string.IsNullOrWhiteSpace(include)) continue;
            var output = reference.Attribute("ReferenceOutputAssembly")?.Value;
            if (string.Equals(output, "false", StringComparison.OrdinalIgnoreCase)) continue;
            var target = Path.GetFullPath(Path.Combine(directory, include.Replace('\\', Path.DirectorySeparatorChar)));
            var relative = Relative(target);
            if (_projects.Contains(relative, StringComparer.Ordinal))
                AddProjectClosure(relative, paths);
        }
    }

    private static string StableHash(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes)[..12].ToLowerInvariant();
    }

    private void EnsureSemantics()
    {
        if (_semanticsBuilt) return;
        _semanticsBuilt = true;
        var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        void AddReference(string path)
        {
            if (!File.Exists(path) || !paths.Add(Path.GetFullPath(path))) return;
            try
            {
                _metadataReferences.Add(MetadataReference.CreateFromFile(path));
            }
            catch (Exception error) when (error is IOException or BadImageFormatException
                or UnauthorizedAccessException)
            {
                // A native or malformed asset is not a Roslyn reference; skip it.
            }
        }

        if (AppContext.GetData("TRUSTED_PLATFORM_ASSEMBLIES") is string trusted)
        {
            foreach (var path in trusted.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
                AddReference(path);
        }

        foreach (var project in _projects)
        {
            var projectDirectory = Path.GetDirectoryName(Path.Combine(_root, project))!;
            var assetsPath = Path.Combine(projectDirectory, "obj", "project.assets.json");
            if (File.Exists(assetsPath))
            {
                try
                {
                    using var document = JsonDocument.Parse(File.ReadAllText(assetsPath));
                    var root = document.RootElement;
                    var folders = root.TryGetProperty("packageFolders", out var packageFolders)
                        ? packageFolders.EnumerateObject().Select(item => item.Name).ToList()
                        : new List<string>();
                    if (!root.TryGetProperty("targets", out var targets)
                        || !root.TryGetProperty("libraries", out var libraries))
                        continue;

                    foreach (var target in targets.EnumerateObject())
                    {
                        foreach (var library in target.Value.EnumerateObject())
                        {
                            if (!libraries.TryGetProperty(library.Name, out var libraryInfo)
                                || libraryInfo.GetProperty("type").GetString() != "package")
                                continue;
                            var package = library.Name.Split('/')[0];
                            var relative = libraryInfo.GetProperty("path").GetString();
                            if (string.IsNullOrWhiteSpace(relative)
                                || !library.Value.TryGetProperty("compile", out var compile))
                                continue;
                            foreach (var asset in compile.EnumerateObject())
                            {
                                var assembly = Path.GetFileNameWithoutExtension(asset.Name);
                                if (!string.IsNullOrEmpty(assembly))
                                    _packageByAssembly[assembly] = package;
                                foreach (var folder in folders)
                                {
                                    var candidate = Path.Combine(folder,
                                        relative.Replace('/', Path.DirectorySeparatorChar),
                                        asset.Name.Replace('/', Path.DirectorySeparatorChar));
                                    AddReference(candidate);
                                }
                            }
                        }
                    }
                }
                catch (JsonException)
                {
                    // A stale or partial assets file must not stop source checks.
                }
            }
            else
            {
                AddPackageCacheReferences(projectDirectory, AddReference);
            }
        }
    }

    private static void AddPackageCacheReferences(string projectDirectory, Action<string> addReference)
    {
        var project = Directory.EnumerateFiles(projectDirectory, "*.csproj").FirstOrDefault();
        if (project is null) return;
        var cache = Environment.GetEnvironmentVariable("NUGET_PACKAGES")
            ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                ".nuget", "packages");
        if (!Directory.Exists(cache)) return;

        XDocument document;
        try
        {
            document = XDocument.Parse(File.ReadAllText(project));
        }
        catch (Exception error) when (error is IOException or System.Xml.XmlException)
        {
            return;
        }

        foreach (var reference in document.Descendants()
                     .Where(item => item.Name.LocalName == "PackageReference"))
        {
            var id = reference.Attribute("Include")?.Value;
            var version = reference.Attribute("Version")?.Value
                ?? reference.Elements().FirstOrDefault(item => item.Name.LocalName == "Version")?.Value;
            if (string.IsNullOrWhiteSpace(id) || string.IsNullOrWhiteSpace(version)) continue;
            var package = Path.Combine(cache, id.ToLowerInvariant(), version);
            if (!Directory.Exists(package)) continue;
            foreach (var folder in new[] { "ref", "lib" })
            {
                var root = Path.Combine(package, folder, "net8.0");
                if (!Directory.Exists(root)) continue;
                foreach (var file in Directory.EnumerateFiles(root, "*.dll"))
                    addReference(file);
            }
        }
    }

    private List<(string Path, int Line, string Package)> ManifestPackages()
    {
        var result = new List<(string Path, int Line, string Package)>();
        var manifests = _cfg.Manifests is { Count: > 0 } ? _cfg.Manifests : _projects;
        foreach (var relative in manifests)
        {
            var full = Path.IsPathRooted(relative) ? relative : Path.Combine(_root, relative);
            if (!File.Exists(full)) continue;
            string text;
            try
            {
                text = File.ReadAllText(full);
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException)
            {
                continue;
            }

            XDocument document;
            try
            {
                document = XDocument.Parse(text);
            }
            catch (System.Xml.XmlException)
            {
                continue;
            }

            var path = Path.IsPathRooted(relative) ? Relative(full) : relative.Replace('\\', '/');
            foreach (var reference in document.Descendants()
                         .Where(item => item.Name.LocalName == "PackageReference"))
            {
                var package = reference.Attribute("Include")?.Value;
                if (string.IsNullOrWhiteSpace(package)) continue;
                result.Add((path, LineOf(text, package), package));
            }
        }

        return result;
    }

    private static string NamespaceOf(string text)
    {
        var match = NamespaceDeclaration.Match(text);
        return match.Success ? match.Groups[1].Value : string.Empty;
    }

    private bool IsRepositoryNamespace(string ns)
    {
        return _repositoryNamespaces.Any(candidate =>
            ns.Equals(candidate, StringComparison.Ordinal)
            || ns.StartsWith(candidate + ".", StringComparison.Ordinal)
            || candidate.StartsWith(ns + ".", StringComparison.Ordinal));
    }

    private static bool ReferencesInternalType(string text, string declaredNamespace, string name)
    {
        if (string.IsNullOrWhiteSpace(declaredNamespace)) return false;
        var identifier = $@"\b{Regex.Escape(name)}\b";
        var qualified = $@"\b(?:global::)?{Regex.Escape(declaredNamespace)}\s*\.\s*{Regex.Escape(name)}\b";
        if (Regex.IsMatch(text, qualified)) return true;
        if (!Regex.IsMatch(text, identifier)) return false;
        return UsingDirective.Matches(text).Cast<Match>().Any(match =>
            string.Equals(match.Groups[1].Value, declaredNamespace, StringComparison.Ordinal));
    }

    private Unit? ResolveNamespace(string ns)
    {
        Unit? best = null;
        var bestLength = -1;
        foreach (var (candidate, unit) in _namespaceUnits)
        {
            if ((ns.Equals(candidate, StringComparison.Ordinal) || ns.StartsWith(candidate + ".", StringComparison.Ordinal)) && candidate.Length > bestLength)
            {
                best = unit;
                bestLength = candidate.Length;
            }
        }

        return best;
    }

    private void CheckEdge(Unit from, Unit to, string path, int line, string evidence)
    {
        if (from.Role is "host" or "tooling" or "test") return;

        if (from.Role == "shared-kernel" && to.Role != "shared-kernel")
        {
            Add(D007, $"shared kernel references {to.Id}; the kernel must be a leaf.", path, line, evidence);
        }

        if (from.Role == "contracts")
        {
            if (to.Role == "implementation")
            {
                Add(D002, $"{from.Id} references the implementation unit {to.Id}.", path, line, evidence);
            }
            else if (to.Role == "contracts" && to.Module != from.Module)
            {
                Add(D003, $"{from.Id} references {to.Id}; contracts must be independent.", path, line, evidence);
            }
            else if (to.Role == "host")
            {
                Add(D006, $"{from.Id} references the host unit; contracts must not know how they are hosted.", path, line, evidence);
            }
        }

        if (from.Role == "implementation")
        {
            if (to.Role == "host")
            {
                Add(D006, $"{from.Id} references the host unit.", path, line, evidence);
            }
            else if (to.Role == "implementation" && to.Module != from.Module)
            {
                if (!ClassifyAdapter(D001, path, line, evidence, from, to, null))
                {
                    Add(D001, $"Module {from.Module} imports the implementation unit {to.Id} (expected {to.Module}.contracts).", path, line, evidence);
                }
            }
        }
    }

    private void CheckCycles()
    {
        var graph = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);
        foreach (var edge in _edges)
        {
            var from = UnitById(edge.From);
            var to = UnitById(edge.To);
            if (from?.Module is null || to?.Module is null || from.Module == to.Module) continue;
            if (!graph.TryGetValue(from.Module, out var nexts))
            {
                nexts = new HashSet<string>(StringComparer.Ordinal);
                graph[from.Module] = nexts;
            }

            nexts.Add(to.Module);
        }

        var state = new Dictionary<string, int>(StringComparer.Ordinal);
        var stack = new List<string>();
        var reported = new HashSet<string>(StringComparer.Ordinal);

        void Visit(string node)
        {
            state[node] = 1;
            stack.Add(node);
            foreach (var next in graph.TryGetValue(node, out var nexts) ? nexts.OrderBy(n => n, StringComparer.Ordinal) : Enumerable.Empty<string>())
            {
                if (!state.TryGetValue(next, out var value) || value == 0)
                {
                    Visit(next);
                }
                else if (value == 1)
                {
                    var start = stack.IndexOf(next);
                    var cycle = stack.Skip(start).Append(next).ToList();
                    var key = string.Join(">", cycle);
                    if (reported.Add(key))
                    {
                        var edge = _edges.FirstOrDefault(e => UnitById(e.From)?.Module == node && UnitById(e.To)?.Module == next);
                        Add(D005, $"Circular module dependency: {string.Join(" -> ", cycle)}", edge?.Path ?? string.Empty, edge?.Line ?? 1, string.Empty);
                    }
                }
            }

            stack.RemoveAt(stack.Count - 1);
            state[node] = 2;
        }

        foreach (var node in graph.Keys.OrderBy(n => n, StringComparer.Ordinal).ToList())
        {
            if (!state.TryGetValue(node, out var value) || value == 0) Visit(node);
        }
    }

    private void CheckTransitive()
    {
        var graph = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);
        foreach (var edge in _edges)
        {
            if (!graph.TryGetValue(edge.From, out var nexts))
            {
                nexts = new HashSet<string>(StringComparer.Ordinal);
                graph[edge.From] = nexts;
            }

            nexts.Add(edge.To);
        }

        var direct = _edges
            .GroupBy(edge => edge.From, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Select(edge => edge.To).ToHashSet(StringComparer.Ordinal),
                StringComparer.Ordinal);

        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var edge in _edges)
        {
            var from = UnitById(edge.From);
            var to = UnitById(edge.To);
            if (from is null || to is null || from.Module == to.Module) continue;
            if (from.Role is not ("contracts" or "implementation")) continue;

            var reachable = new HashSet<string>(StringComparer.Ordinal) { to.Id };
            var queue = new Queue<string>();
            queue.Enqueue(to.Id);
            while (queue.Count > 0)
            {
                var node = queue.Dequeue();
                if (!graph.TryGetValue(node, out var nexts)) continue;
                foreach (var next in nexts)
                {
                    if (reachable.Add(next)) queue.Enqueue(next);
                }
            }

            foreach (var id in reachable.OrderBy(x => x, StringComparer.Ordinal))
            {
                var target = UnitById(id);
                if (target is null || target.Module == from.Module || target.Role != "implementation") continue;
                if (direct.TryGetValue(from.Id, out var directTargets) && directTargets.Contains(target.Id)) continue;
                if (!seen.Add(from.Id + ">" + target.Id)) continue;
                Add(D008, $"{from.Id} reaches the implementation unit {target.Id} transitively through {to.Id}.", edge.Path, edge.Line, edge.Evidence);
            }
        }
    }

    private void CheckVisibility()
    {
        var internals = new List<(string Name, string Namespace, Unit Unit, string Path, int Line)>();
        var publics = new Dictionary<string, (Unit Unit, string Path, int Line)>(StringComparer.Ordinal);

        foreach (var (path, text) in _files.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (unit.Role != "implementation") continue;
            var declaredNamespace = NamespaceOf(text);
            foreach (Match match in InternalType.Matches(text))
            {
                internals.Add((match.Groups[1].Value, declaredNamespace, unit, path, LineOf(text, match.Value)));
            }

            foreach (Match match in PublicType.Matches(text))
            {
                publics[match.Groups[1].Value] = (unit, path, LineOf(text, match.Value));
            }
        }

        foreach (var (path, text) in _files.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (unit.Role is "host" or "tooling" or "test") continue;

            foreach (var declaration in internals)
            {
                if (declaration.Unit.Module == unit.Module) continue;
                if (!ReferencesInternalType(text, declaration.Namespace, declaration.Name)) continue;
                if (!ClassifyAdapter(D009, path, LineOf(text, declaration.Name), declaration.Name, unit, declaration.Unit, null))
                {
                    Add(D009, $"{unit.Id} references the internal type {declaration.Name} from module {declaration.Unit.Module}.",
                        path, LineOf(text, declaration.Name), declaration.Namespace + "." + declaration.Name);
                }
            }
        }

        foreach (var (path, text) in _files.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (unit.Role is "host" or "tooling" or "test") continue;

            foreach (var (name, declaration) in publics)
            {
                if (declaration.Unit.Module == unit.Module) continue;
                if (!Regex.IsMatch(text, $@"\b{Regex.Escape(name)}\b")) continue;
                if (!ClassifyPublicApi(L003, declaration.Path, declaration.Line, name, declaration.Unit))
                {
                    Add(L003, $"implementation unit {declaration.Unit.Id} publishes the public type {name} outside the module", declaration.Path, declaration.Line, name);
                }
            }
        }
    }

    private void CheckContracts()
    {
        foreach (var (path, text) in _files.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (unit.Role != "contracts") continue;

            foreach (Match match in PropertySetter.Matches(text))
            {
                Add(C001, $"Contract type in {unit.Id} exposes a mutable property ({match.Value.Trim()}).", path, LineOf(text, match.Value), match.Value.Trim());
            }

            foreach (Match match in PublicField.Matches(text))
            {
                Add(C001, $"Contract type in {unit.Id} exposes a public field ({match.Value.Trim()}).", path, LineOf(text, match.Value), match.Value.Trim());
            }

            foreach (Match match in CollectionMember.Matches(text))
            {
                Add(C002, $"Contract type in {unit.Id} exposes a mutable collection ({match.Value}).", path, LineOf(text, match.Value), match.Value);
            }

            foreach (Match match in Ambient.Matches(text))
            {
                Add(C004, $"contracts unit {unit.Id} reads ambient state ({match.Value}).", path, LineOf(text, match.Value), match.Value);
            }

            foreach (Match match in Persistence.Matches(text))
            {
                Add(C005, $"contracts unit {unit.Id} exposes a persistence concern ({match.Value}).", path, LineOf(text, match.Value), match.Value);
            }

            foreach (Match match in Untyped.Matches(text))
            {
                Add(C006, $"Contract type in {unit.Id} has an untyped member ({match.Value.Trim()}).", path, LineOf(text, match.Value), match.Value.Trim());
            }

            foreach (Match match in Framework.Matches(text))
            {
                Add(L002, $"contracts unit {unit.Id} exposes a framework type ({match.Value}).", path, LineOf(text, match.Value), match.Value);
            }

            foreach (Match match in PublicType.Matches(text))
            {
                var name = match.Groups[1].Value;
                var before = text[..match.Index];
                var window = before.Length > 200 ? before[^200..] : before;
                if (!window.Contains("/// <summary>", StringComparison.Ordinal))
                {
                    Add(G003, $"Contract type {name} has no documentation.", path, LineOf(text, match.Value), name);
                }
            }
        }
    }

    private void CheckLayering()
    {
        foreach (var (path, text) in _files.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            var isInfrastructurePath = path.Split('/').Any(segment =>
                string.Equals(segment, "Infrastructure", StringComparison.OrdinalIgnoreCase));
            if (unit.Role != "implementation" || isInfrastructurePath) continue;
            // L001 is a dependency edge. A using directive is a conservative,
            // identifier-safe approximation; a bare name or string is not an import.
            foreach (Match match in UsingDirective.Matches(text))
            {
                var ns = match.Groups[1].Value;
                if (!PersistenceNamespace.IsMatch(ns)) continue;
                if (!ClassifyAdapter(L001, path, LineOf(text, match.Value), match.Value.Trim(), unit, null, ns, "."))
                {
                    Add(L001, $"{unit.Id} imports infrastructure ({ns}) outside infrastructure/.", path, LineOf(text, match.Value), match.Value.Trim());
                }
            }
        }
    }

    private void CheckSql()
    {
        var modules = _cfg.Units.Where(u => u.Module is not null).Select(u => u.Module!).ToHashSet(StringComparer.Ordinal);
        foreach (var (path, text) in _files.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            foreach (Match literal in StringLiteral.Matches(text))
            {
                foreach (Match table in SqlTable.Matches(literal.Groups[1].Value))
                {
                    var prefix = table.Groups[1].Value.Split('_')[0];
                    if (!modules.Contains(prefix) || prefix == unit.Module) continue;
                    Add(A001, $"{unit.Id} queries the {prefix} schema ({table.Groups[1].Value}); each module owns its own tables.", path, LineOf(text, literal.Value), table.Groups[1].Value);
                }
            }
        }
    }

    private static string CallName(ExpressionSyntax expression) => expression switch
    {
        IdentifierNameSyntax identifier => identifier.Identifier.ValueText,
        GenericNameSyntax generic => generic.Identifier.ValueText,
        MemberAccessExpressionSyntax member => CallName(member.Name),
        MemberBindingExpressionSyntax binding => CallName(binding.Name),
        _ => string.Empty,
    };

    private static string TypeLeaf(TypeSyntax? type)
    {
        if (type is null) return string.Empty;
        return type switch
        {
            IdentifierNameSyntax identifier => identifier.Identifier.ValueText,
            GenericNameSyntax generic => generic.Identifier.ValueText,
            QualifiedNameSyntax qualified => TypeLeaf(qualified.Right),
            AliasQualifiedNameSyntax alias => TypeLeaf(alias.Name),
            NullableTypeSyntax nullable => TypeLeaf(nullable.ElementType),
            ArrayTypeSyntax array => TypeLeaf(array.ElementType),
            _ => type.DescendantTokens().LastOrDefault(token => token.IsKind(SyntaxKind.IdentifierToken)).ValueText ?? string.Empty,
        };
    }

    private static bool IsModuleOwnedRole(string role) =>
        role is "implementation" or "host" or "adapter" or "port";

    private void CheckNamedArguments()
    {
        // C# supports native labels: parameterName: value. Roslyn parses declarations and
        // calls without executing the product or depending on a project build graph.
        var methods = new Dictionary<string, List<(string Owner, string[] Names, bool HasParams)>>(StringComparer.Ordinal);
        var constructors = new Dictionary<string, List<(string[] Names, bool HasParams)>>(StringComparer.Ordinal);
        var declaredTypes = new HashSet<string>(StringComparer.Ordinal);
        var trees = new Dictionary<string, SyntaxNode>(StringComparer.Ordinal);

        void AddMethod(string name, string owner, ParameterListSyntax parameters)
        {
            var declared = parameters.Parameters;
            var extension = declared.Count > 0 && declared[0].Modifiers.Any(token => token.IsKind(SyntaxKind.ThisKeyword));
            var names = declared.Skip(extension ? 1 : 0).Select(parameter => parameter.Identifier.ValueText).ToArray();
            var hasParams = declared.Any(parameter => parameter.Modifiers.Any(token => token.IsKind(SyntaxKind.ParamsKeyword)));
            if (!methods.TryGetValue(name, out var entries))
                methods[name] = entries = new List<(string Owner, string[] Names, bool HasParams)>();
            if (!entries.Any(entry => entry.Owner == owner && entry.Names.SequenceEqual(names)))
                entries.Add((owner, names, hasParams));
        }

        foreach (var path in _files.Keys.OrderBy(key => key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (unit.Role is not ("contracts" or "implementation" or "host" or "adapter" or "port")) continue;
            var syntax = _syntax[path];
            if (IsModuleOwnedRole(unit.Role)) trees[path] = syntax;
            foreach (var declaration in syntax.DescendantNodes().OfType<TypeDeclarationSyntax>())
                declaredTypes.Add(declaration.Identifier.ValueText);
            foreach (var method in syntax.DescendantNodes().OfType<MethodDeclarationSyntax>())
                AddMethod(method.Identifier.ValueText, method.Ancestors().OfType<TypeDeclarationSyntax>().FirstOrDefault()?.Identifier.ValueText ?? path, method.ParameterList);
            foreach (var local in syntax.DescendantNodes().OfType<LocalFunctionStatementSyntax>())
                AddMethod(local.Identifier.ValueText, path + "::local", local.ParameterList);
            foreach (var constructor in syntax.DescendantNodes().OfType<ConstructorDeclarationSyntax>())
            {
                if (constructor.Parent is not TypeDeclarationSyntax owner) continue;
                var parameters = constructor.ParameterList.Parameters;
                var names = parameters.Select(parameter => parameter.Identifier.ValueText).ToArray();
                var hasParams = parameters.Any(parameter => parameter.Modifiers.Any(token => token.IsKind(SyntaxKind.ParamsKeyword)));
                if (!constructors.TryGetValue(owner.Identifier.ValueText, out var entries))
                    constructors[owner.Identifier.ValueText] = entries = new List<(string[] Names, bool HasParams)>();
                if (!entries.Any(entry => entry.Names.SequenceEqual(names))) entries.Add((names, hasParams));
            }
            foreach (var declaration in syntax.DescendantNodes().OfType<ClassDeclarationSyntax>())
            {
                if (declaration.ParameterList is null) continue;
                AddPrimaryConstructor(declaration.Identifier.ValueText, declaration.ParameterList);
            }
            foreach (var declaration in syntax.DescendantNodes().OfType<RecordDeclarationSyntax>())
            {
                if (declaration.ParameterList is null) continue;
                AddPrimaryConstructor(declaration.Identifier.ValueText, declaration.ParameterList);
            }

            void AddPrimaryConstructor(string owner, ParameterListSyntax parameterList)
            {
                var names = parameterList.Parameters.Select(parameter => parameter.Identifier.ValueText).ToArray();
                var hasParams = parameterList.Parameters.Any(parameter =>
                    parameter.Modifiers.Any(token => token.IsKind(SyntaxKind.ParamsKeyword)));
                if (!constructors.TryGetValue(owner, out var entries))
                    constructors[owner] = entries = new List<(string[] Names, bool HasParams)>();
                if (!entries.Any(entry => entry.Names.SequenceEqual(names))) entries.Add((names, hasParams));
            }
        }

        foreach (var (path, syntax) in trees)
        {
            var unit = _fileUnits[path];
            var sourceLines = _files[path].Split(new[] { "\r\n", "\n" }, StringSplitOptions.None);
            foreach (var invocation in syntax.DescendantNodes().OfType<InvocationExpressionSyntax>())
            {
                var name = CallName(invocation.Expression);
                if (string.IsNullOrEmpty(name) || !methods.TryGetValue(name, out var candidates)) continue;
                var currentType = invocation.Ancestors().OfType<TypeDeclarationSyntax>().FirstOrDefault();
                var receiverType = invocation.Expression switch
                {
                    IdentifierNameSyntax => currentType?.Identifier.ValueText,
                    MemberAccessExpressionSyntax member => ResolveReceiverType(member.Expression, invocation, currentType, declaredTypes),
                    _ => null,
                };
                if (string.IsNullOrEmpty(receiverType)) continue;
                var matching = candidates.Where(candidate => candidate.Owner == receiverType).ToList();
                if (matching.Count == 0) continue;
                var unlabeled = new List<string>();
                var firstLine = 0;
                foreach (var argument in invocation.ArgumentList.Arguments)
                {
                    if (argument.NameColon is not null) continue;
                    var index = invocation.ArgumentList.Arguments.IndexOf(argument);
                    var viable = matching.Where(candidate =>
                        index < candidate.Names.Length || candidate.HasParams && candidate.Names.Length > 0).ToList();
                    if (viable.Count == 0) continue;
                    // Expanded params values have no independent destination name. Require the
                    // caller to construct an array and pass that array under the params label.
                    if (viable.All(candidate => candidate.HasParams && index >= candidate.Names.Length - 1))
                    {
                        var paramsLabels = viable.Where(candidate => candidate.Names.Length > 0)
                            .Select(candidate => candidate.Names[^1]).Distinct(StringComparer.Ordinal).ToList();
                        var paramsName = paramsLabels.Count == 1 ? paramsLabels[0] : "the declared params parameter";
                        var expanded = invocation.ArgumentList.Arguments.Skip(index)
                            .Select(item => item.Expression.ToString()).ToList();
                        unlabeled.Add(paramsName + ": new[] { " + string.Join(", ", expanded) + " }");
                        break;
                    }
                    var labels = viable.Where(candidate => index < candidate.Names.Length)
                        .Select(candidate => candidate.Names[index]).Distinct(StringComparer.Ordinal).ToList();
                    var hint = labels.Count == 1 ? labels[0] : "the declared parameter";
                    unlabeled.Add(hint + ": " + argument.Expression);
                    if (firstLine == 0)
                        firstLine = argument.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
                }
                if (unlabeled.Count > 0)
                {
                    var line = firstLine > 0 ? firstLine :
                        invocation.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
                    var evidence = line > 0 && line <= sourceLines.Length ? sourceLines[line - 1].Trim() : invocation.ToString();
                    Add(D017, $"{unit.Id} calls {name}() with unlabeled arguments; label every value: " +
                        string.Join(", ", unlabeled) + ".",
                        path, line, evidence);
                }
            }

            foreach (var creation in syntax.DescendantNodes().OfType<ObjectCreationExpressionSyntax>())
                CheckCreation(path, unit, sourceLines, constructors, TypeLeaf(creation.Type), creation.ArgumentList?.Arguments);
            foreach (var creation in syntax.DescendantNodes().OfType<ImplicitObjectCreationExpressionSyntax>())
                CheckCreation(path, unit, sourceLines, constructors, string.Empty, creation.ArgumentList.Arguments);
        }
    }

    private void CheckComposition()
    {
        foreach (var (path, syntax) in _syntax.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (!CompositionRoles.Contains(unit.Role)) continue;
            var lines = SourceLines(path);
            var model = SemanticModelFor(path);
            var seen = new HashSet<(string Rule, int Line)>();

            if (unit.Role == "host")
            {
                foreach (var invocation in syntax.DescendantNodes().OfType<InvocationExpressionSyntax>())
                {
                    var name = CallName(invocation.Expression);
                    if (!DiscoveryMethods.Contains(name)) continue;
                    var operation = model.GetOperation(invocation) as IInvocationOperation;
                    var target = operation?.TargetMethod;
                    var containing = target?.ContainingType?.ToDisplayString() ?? string.Empty;
                    var receiver = (invocation.Expression as MemberAccessExpressionSyntax)?.Expression;
                    var recognized = name switch
                    {
                        "GetTypes" or "GetExportedTypes" =>
                            containing.Contains("Assembly", StringComparison.Ordinal)
                            || IsAssemblyReceiver(receiver, model),
                        "GetAssemblies" =>
                            containing.Contains("AppDomain", StringComparison.Ordinal)
                            || receiver?.ToString().Contains("AppDomain.CurrentDomain", StringComparison.Ordinal) == true,
                        "RegisterAssemblyTypes" => true,
                        "Scan" or "FromAssemblyOf" or "FromAssemblies" or "AddClasses" =>
                            IsServiceCollectionReceiver(receiver, model)
                            || containing.Contains("Scrutor", StringComparison.Ordinal),
                        _ => false,
                    };
                    if (!recognized) continue;
                    var line = LineOf(invocation);
                    if (!seen.Add((D013, line))) continue;
                    Add(D013, $"composition host {unit.Id} discovers components with {name}; register and construct each module-owned component explicitly.",
                        path, line, SourceLine(lines, line, invocation.ToString()));
                }

                foreach (var member in syntax.DescendantNodes().OfType<MemberAccessExpressionSyntax>())
                {
                    if (member.Name.Identifier.ValueText != "DefinedTypes") continue;
                    if (!IsAssemblyReceiver(member.Expression, model)) continue;
                    var line = LineOf(member);
                    if (!seen.Add((D013, line))) continue;
                    Add(D013, $"composition host {unit.Id} discovers components with DefinedTypes; register and construct each module-owned component explicitly.",
                        path, line, SourceLine(lines, line, member.ToString()));
                }
            }

            foreach (var field in syntax.DescendantNodes().OfType<FieldDeclarationSyntax>())
                CheckInjectionAttributes(field.AttributeLists, field, path, unit, lines, seen);
            foreach (var property in syntax.DescendantNodes().OfType<PropertyDeclarationSyntax>())
                CheckInjectionAttributes(property.AttributeLists, property, path, unit, lines, seen);
        }
    }

    private void CheckInjectionAttributes(SyntaxList<AttributeListSyntax> attributes,
        SyntaxNode declaration, string path, Unit unit, string[] lines,
        HashSet<(string Rule, int Line)> seen)
    {
        foreach (var attribute in attributes.SelectMany(list => list.Attributes))
        {
            var name = AttributeName(attribute);
            if (!InjectionAttributes.Contains(name)) continue;
            var line = LineOf(attribute);
            if (!seen.Add((D014, line))) continue;
            Add(D014, $"{unit.Id} receives a dependency through property or field injection; declare it in the constructor and supply it from the composition boundary.",
                path, line, SourceLine(lines, line, attribute + " " + declaration));
        }
    }

    private void CheckNaming()
    {
        foreach (var (path, syntax) in _syntax.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (!NamingRoles.Contains(unit.Role)) continue;
            var lines = SourceLines(path);
            foreach (var declaration in syntax.DescendantNodes().OfType<BaseTypeDeclarationSyntax>())
            {
                if (IsGenerated(path, declaration)) continue;
                var name = declaration.Identifier.ValueText.TrimStart('@');
                if (string.IsNullOrEmpty(name)) continue;
                var line = LineOf(declaration);
                var evidence = SourceLine(lines, line, declaration.Identifier.ValueText);
                if (!IsPascalCase(name))
                {
                    Add(N001, $"{unit.Id} declares the type {name} without the .NET PascalCase type-name convention.",
                        path, line, evidence);
                }
                if (GenericTypeNames.Contains(name)
                    || GenericTypeSuffixes.Any(suffix => name.EndsWith(suffix, StringComparison.Ordinal)))
                {
                    Add(N002, $"{unit.Id} names the type {name} after a generic role; name the responsibility or domain concept instead.",
                        path, line, evidence);
                }
            }
        }
    }

    private static bool IsAssemblyReceiver(ExpressionSyntax? receiver, SemanticModel model)
    {
        if (receiver is null) return false;
        var text = receiver.ToString();
        if (text.Contains("Assembly", StringComparison.Ordinal)
            || text.Contains("GetExecutingAssembly", StringComparison.Ordinal)
            || text.Contains("GetEntryAssembly", StringComparison.Ordinal)
            || text.Contains("GetCallingAssembly", StringComparison.Ordinal)) return true;
        var type = model.GetTypeInfo(receiver).Type?.ToDisplayString() ?? string.Empty;
        return type.Contains("System.Reflection.Assembly", StringComparison.Ordinal);
    }

    private static bool IsServiceCollectionReceiver(ExpressionSyntax? receiver, SemanticModel model)
    {
        if (receiver is null) return false;
        var type = model.GetTypeInfo(receiver).Type?.ToDisplayString() ?? string.Empty;
        return type.Contains("IServiceCollection", StringComparison.Ordinal)
               || type.Contains("ServiceCollection", StringComparison.Ordinal);
    }

    private static string AttributeName(AttributeSyntax attribute)
    {
        var name = attribute.Name.ToString().Split('.').LastOrDefault() ?? string.Empty;
        return name.EndsWith("Attribute", StringComparison.Ordinal)
            ? name[..^"Attribute".Length]
            : name;
    }

    private static bool IsGenerated(string path, BaseTypeDeclarationSyntax declaration)
    {
        if (path.EndsWith(".g.cs", StringComparison.OrdinalIgnoreCase)
            || path.EndsWith(".generated.cs", StringComparison.OrdinalIgnoreCase)
            || path.EndsWith(".designer.cs", StringComparison.OrdinalIgnoreCase)) return true;
        return declaration.AttributeLists.SelectMany(list => list.Attributes)
            .Any(attribute => AttributeName(attribute) == "GeneratedCode");
    }

    private static bool IsPascalCase(string name) =>
        name.Length > 0 && char.IsUpper(name[0]) && name.All(char.IsLetterOrDigit);

    private void CheckConfiguration()
    {
        foreach (var (path, syntax) in _syntax.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (!ConfigReadRoles.Contains(unit.Role)) continue;
            var lines = SourceLines(path);
            var model = SemanticModelFor(path);
            var seen = new HashSet<int>();

            foreach (var invocation in syntax.DescendantNodes().OfType<InvocationExpressionSyntax>())
            {
                var name = CallName(invocation.Expression);
                if (name is not ("GetEnvironmentVariable" or "GetEnvironmentVariables")) continue;
                var operation = model.GetOperation(invocation) as IInvocationOperation;
                var containing = operation?.TargetMethod?.ContainingType?.ToDisplayString() ?? string.Empty;
                var receiver = (invocation.Expression as MemberAccessExpressionSyntax)?.Expression;
                if (!containing.Contains("System.Environment", StringComparison.Ordinal)
                    && receiver?.ToString() != "Environment") continue;
                var line = LineOf(invocation);
                if (!seen.Add(line)) continue;
                var key = invocation.ArgumentList.Arguments.FirstOrDefault()?.Expression is { } argument
                    ? LiteralText(argument)
                    : string.Empty;
                Add(A005, $"{unit.Id} reads {(key.Length > 0 ? $"the environment key {key}" : "the process environment")} directly; resolve it at the composition root and pass the value into the component.",
                    path, line, SourceLine(lines, line, invocation.ToString()));
            }

            foreach (var member in syntax.DescendantNodes().OfType<MemberAccessExpressionSyntax>())
            {
                var name = member.Name.Identifier.ValueText;
                if (name is not ("AppSettings" or "ConnectionStrings")) continue;
                var receiver = member.Expression.ToString();
                if (receiver != "ConfigurationManager"
                    && !receiver.EndsWith(".ConfigurationManager", StringComparison.Ordinal)) continue;
                var line = LineOf(member);
                if (!seen.Add(line)) continue;
                Add(A005, $"{unit.Id} reads {name} through ConfigurationManager directly; resolve it at the composition root and pass the value into the component.",
                    path, line, SourceLine(lines, line, member.ToString()));
            }
        }
    }

    private void CheckFunctionalCapture()
    {
        foreach (var (path, syntax) in _syntax.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (!FunctionalRoles.Contains(unit.Role)) continue;
            var lines = SourceLines(path);
            var model = SemanticModelFor(path);
            var seen = new HashSet<(string Rule, int Line, string Name)>();

            foreach (var scope in FunctionalScopes(syntax))
            {
                var ownParameters = FunctionalParameters(scope);
                foreach (var identifier in scope.DescendantNodes()
                             .OfType<IdentifierNameSyntax>()
                             .Where(node => !InsideNestedFunctionalScope(node, scope)))
                {
                    if (identifier.Parent is MemberAccessExpressionSyntax member && member.Name == identifier)
                        continue;
                    if (identifier.Parent is MemberBindingExpressionSyntax)
                        continue;
                    var name = identifier.Identifier.ValueText;
                    if (string.IsNullOrEmpty(name) || ownParameters.Contains(name)
                        || !ContainsToken(name, FunctionalTokens)) continue;
                    var symbol = model.GetSymbolInfo(identifier).Symbol;
                    var captured = false;
                    if (symbol is IFieldSymbol field)
                    {
                        captured = field.IsStatic && !field.IsConst;
                    }
                    else if (symbol is IPropertySymbol property)
                    {
                        captured = property.IsStatic;
                    }
                    else if (symbol is ILocalSymbol local)
                    {
                        captured = local.DeclaringSyntaxReferences
                            .Any(reference => !scope.Span.Contains(reference.Span));
                    }

                    if (!captured) continue;
                    var line = LineOf(identifier);
                    if (!seen.Add((D015, line, name))) continue;
                    Add(D015, $"{unit.Id} captures the module-owned dependency {name} from an enclosing scope; pass it as a parameter or supply it at the composition boundary.",
                        path, line, SourceLine(lines, line, identifier.ToString()));
                }
            }

            if (_cfg.PartialHelpers is null || _cfg.PartialHelpers.Count == 0) continue;
            var helpers = _cfg.PartialHelpers.ToHashSet(StringComparer.Ordinal);
            foreach (var invocation in syntax.DescendantNodes().OfType<InvocationExpressionSyntax>())
            {
                var name = CallName(invocation.Expression);
                if (!helpers.Contains(name)) continue;
                var dependency = invocation.ArgumentList.Arguments
                    .Select(argument => DependencyName(argument.Expression, model))
                    .FirstOrDefault(candidate => !string.IsNullOrEmpty(candidate));
                if (string.IsNullOrEmpty(dependency)) continue;
                var line = LineOf(invocation);
                if (!seen.Add((D016, line, dependency))) continue;
                Add(D016, $"{unit.Id} partially applies the module-owned dependency {dependency} inside a component; bind it at the composition boundary or keep it as a parameter.",
                    path, line, SourceLine(lines, line, invocation.ToString()));
            }
        }
    }

    private static IEnumerable<SyntaxNode> FunctionalScopes(SyntaxNode syntax) =>
        syntax.DescendantNodes().Where(node =>
            node is LambdaExpressionSyntax or AnonymousMethodExpressionSyntax or LocalFunctionStatementSyntax);

    private static HashSet<string> FunctionalParameters(SyntaxNode scope)
    {
        var names = new HashSet<string>(StringComparer.Ordinal);
        switch (scope)
        {
            case SimpleLambdaExpressionSyntax simple:
                names.Add(simple.Parameter.Identifier.ValueText);
                break;
            case ParenthesizedLambdaExpressionSyntax parenthesized:
                foreach (var parameter in parenthesized.ParameterList.Parameters)
                    names.Add(parameter.Identifier.ValueText);
                break;
            case AnonymousMethodExpressionSyntax anonymous:
                foreach (var parameter in anonymous.ParameterList?.Parameters ?? default)
                    names.Add(parameter.Identifier.ValueText);
                break;
            case LocalFunctionStatementSyntax local:
                foreach (var parameter in local.ParameterList.Parameters)
                    names.Add(parameter.Identifier.ValueText);
                break;
        }

        return names;
    }

    private static bool InsideNestedFunctionalScope(SyntaxNode node, SyntaxNode scope)
    {
        var ancestor = node.Ancestors().FirstOrDefault(candidate =>
            candidate is LambdaExpressionSyntax or AnonymousMethodExpressionSyntax or LocalFunctionStatementSyntax);
        return ancestor is not null && ancestor != scope;
    }

    private static bool ContainsToken(string name, HashSet<string> tokens)
    {
        var snake = Regex.Replace(name, "(?<=[a-z0-9])(?=[A-Z])", "_").ToLowerInvariant();
        return Regex.Split(snake, "[^a-z0-9]+").Any(tokens.Contains);
    }

    private static string? DependencyName(ExpressionSyntax expression, SemanticModel model)
    {
        foreach (var identifier in expression.DescendantNodesAndSelf().OfType<IdentifierNameSyntax>())
        {
            var symbol = model.GetSymbolInfo(identifier).Symbol;
            var name = symbol switch
            {
                IFieldSymbol field when !field.IsConst => field.Name,
                IPropertySymbol property => property.Name,
                ILocalSymbol local => local.Name,
                IParameterSymbol parameter => parameter.Name,
                _ => string.Empty,
            };
            if (string.IsNullOrEmpty(name) || !ContainsToken(name, FunctionalTokens)) continue;
            return name;
        }

        return null;
    }

    private static string LiteralText(ExpressionSyntax expression) => expression switch
    {
        LiteralExpressionSyntax literal when literal.IsKind(SyntaxKind.StringLiteralExpression)
            => literal.Token.ValueText,
        LiteralExpressionSyntax literal => literal.Token.Text,
        InterpolatedStringExpressionSyntax interpolated => interpolated.ToString(),
        _ => string.Empty,
    };

    private void CheckLifecycle()
    {
        var registrations = new List<Registration>();
        foreach (var (path, syntax) in _syntax.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (unit.Role != "host") continue;
            var lines = SourceLines(path);
            foreach (var invocation in syntax.DescendantNodes().OfType<InvocationExpressionSyntax>())
            {
                var registration = RegistrationFor(invocation, path, lines);
                if (registration is not null) registrations.Add(registration);
            }
        }

        var lifetimes = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var registration in registrations)
        {
            lifetimes[registration.Service] = registration.Lifetime;
            lifetimes[registration.Implementation] = registration.Lifetime;
        }

        foreach (var registration in registrations)
        {
            var type = FindClass(registration.Implementation);
            if (type is null) continue;
            if (registration.Lifetime == "transient" && IsStateless(type))
            {
                Add(A007, $"the host registers the stateless shared service {registration.Implementation} as transient; share it at the longest appropriate lifetime.",
                    registration.Path, registration.Line, registration.Evidence);
            }

            if (registration.Lifetime != "shared") continue;
            if (OwnsMutableContainer(type))
            {
                Add(A009, $"the host shares {registration.Implementation}, which owns mutable state; give that state an explicit owner, isolation boundary and concurrency policy.",
                    registration.Path, registration.Line, registration.Evidence);
            }

            foreach (var dependency in ConstructorDependencies(type))
            {
                if (!lifetimes.TryGetValue(dependency, out var lifetime) || lifetime != "scoped") continue;
                Add(A008, $"the host shares {registration.Implementation}, which captures the scoped dependency {dependency}; shorten the lifetime or resolve it at the correct scope boundary.",
                    registration.Path, registration.Line, registration.Evidence);
            }
        }
    }

    private static Registration? RegistrationFor(InvocationExpressionSyntax invocation,
        string path, string[] lines)
    {
        var name = CallName(invocation.Expression);
        var lifetime = name switch
        {
            "AddSingleton" or "TryAddSingleton" => "shared",
            "AddScoped" or "TryAddScoped" => "scoped",
            "AddTransient" or "TryAddTransient" => "transient",
            _ => string.Empty,
        };
        if (lifetime.Length == 0) return null;

        var generic = invocation.Expression switch
        {
            GenericNameSyntax direct => direct,
            MemberAccessExpressionSyntax member => member.Name as GenericNameSyntax,
            _ => null,
        };
        var types = generic?.TypeArgumentList.Arguments.ToList() ?? new List<TypeSyntax>();
        if (types.Count == 0)
        {
            foreach (var argument in invocation.ArgumentList.Arguments)
            {
                if (argument.Expression is TypeOfExpressionSyntax typeOf)
                    types.Add(typeOf.Type);
            }
        }

        if (types.Count is not (1 or 2)) return null;
        var implementation = TypeLeaf(types[^1]);
        var service = TypeLeaf(types[0]);
        if (string.IsNullOrWhiteSpace(implementation) || string.IsNullOrWhiteSpace(service)) return null;
        var line = LineOf(invocation);
        return new Registration(service, implementation, lifetime, path, line,
            SourceLine(lines, line, invocation.ToString()));
    }

    private ClassDeclarationSyntax? FindClass(string name)
    {
        if (!_types.TryGetValue(name, out var types)) return null;
        var classes = types.OfType<ClassDeclarationSyntax>().ToList();
        return classes.Count == 1 ? classes[0] : null;
    }

    private static bool IsStateless(ClassDeclarationSyntax type)
    {
        // Behaviorally stateless: no mutable instance state, one required construction path,
        // and readonly constructor-injected collaborators. D011 remains responsible for reporting
        // optional constructor parameters; A007 only declines to classify such a class as stateless.
        var constructors = type.Members.OfType<ConstructorDeclarationSyntax>()
            .Where(constructor => !constructor.Modifiers.Any(token => token.IsKind(SyntaxKind.StaticKeyword)))
            .ToList();
        var primary = type.ParameterList;
        if (primary is not null && constructors.Count > 0) return false;
        if (primary is null && constructors.Count > 1) return false;

        var parameters = primary?.Parameters
            ?? constructors.FirstOrDefault()?.ParameterList.Parameters
            ?? default;
        if (parameters.Any(parameter => parameter.Default is not null
                || parameter.Modifiers.Any(token => token.IsKind(SyntaxKind.ParamsKeyword))))
            return false;

        var fields = type.Members.OfType<FieldDeclarationSyntax>().ToList();
        var properties = type.Members.OfType<PropertyDeclarationSyntax>().ToList();
        foreach (var field in fields)
        {
            var isStatic = field.Modifiers.Any(token => token.IsKind(SyntaxKind.StaticKeyword)
                || token.IsKind(SyntaxKind.ConstKeyword));
            var isReadonly = field.Modifiers.Any(token => token.IsKind(SyntaxKind.ReadOnlyKeyword)
                || token.IsKind(SyntaxKind.ConstKeyword));
            if (!isReadonly && !isStatic) return false;
            if (isStatic && !isReadonly) return false;
            if (IsMutableContainer(field.Declaration.Type)) return false;
        }

        foreach (var property in properties)
        {
            if (IsMutableContainer(property.Type)) return false;
            var hasSetter = property.AccessorList?.Accessors.Any(accessor =>
                accessor.IsKind(SyntaxKind.SetAccessorDeclaration)
                || accessor.IsKind(SyntaxKind.InitAccessorDeclaration)) == true;
            if (hasSetter) return false;
        }

        var names = new HashSet<string>(StringComparer.Ordinal);
        foreach (var field in fields)
            foreach (var variable in field.Declaration.Variables)
                names.Add(variable.Identifier.ValueText);
        foreach (var property in properties) names.Add(property.Identifier.ValueText);

        foreach (var assignment in type.DescendantNodes().OfType<AssignmentExpressionSyntax>())
        {
            if (!names.Contains(AssignmentTargetName(assignment.Left))) continue;
            if (!assignment.IsKind(SyntaxKind.SimpleAssignmentExpression)) return false;
            var constructor = constructors.FirstOrDefault();
            if (constructor?.Body is null || !constructor.Body.Span.Contains(assignment.Span)) return false;
        }

        foreach (var increment in type.DescendantNodes().OfType<PrefixUnaryExpressionSyntax>()
                     .Where(node => node.IsKind(SyntaxKind.PreIncrementExpression)
                         || node.IsKind(SyntaxKind.PreDecrementExpression)))
        {
            if (names.Contains(AssignmentTargetName(increment.Operand))) return false;
        }
        foreach (var increment in type.DescendantNodes().OfType<PostfixUnaryExpressionSyntax>()
                     .Where(node => node.IsKind(SyntaxKind.PostIncrementExpression)
                         || node.IsKind(SyntaxKind.PostDecrementExpression)))
        {
            if (names.Contains(AssignmentTargetName(increment.Operand))) return false;
        }

        return true;
    }

    private static string AssignmentTargetName(ExpressionSyntax? expression) => expression switch
    {
        IdentifierNameSyntax identifier => identifier.Identifier.ValueText,
        MemberAccessExpressionSyntax member when member.Expression is ThisExpressionSyntax =>
            member.Name.Identifier.ValueText,
        _ => string.Empty,
    };

    private static IEnumerable<string> ConstructorDependencies(ClassDeclarationSyntax type)
    {
        var names = new HashSet<string>(StringComparer.Ordinal);
        if (type.ParameterList is not null)
        {
            foreach (var parameter in type.ParameterList.Parameters)
            {
                var name = TypeLeaf(parameter.Type);
                if (name.Length > 0) names.Add(name);
            }
        }

        foreach (var constructor in type.Members.OfType<ConstructorDeclarationSyntax>())
        {
            foreach (var parameter in constructor.ParameterList.Parameters)
            {
                var name = TypeLeaf(parameter.Type);
                if (name.Length > 0) names.Add(name);
            }
        }

        return names;
    }

    private static bool OwnsMutableContainer(ClassDeclarationSyntax type)
    {
        foreach (var field in type.Members.OfType<FieldDeclarationSyntax>())
        {
            if (field.Modifiers.Any(token => token.IsKind(SyntaxKind.StaticKeyword)
                    || token.IsKind(SyntaxKind.ConstKeyword))) continue;
            if (IsMutableContainer(field.Declaration.Type)) return true;
        }
        foreach (var property in type.Members.OfType<PropertyDeclarationSyntax>())
        {
            if (property.Modifiers.Any(token => token.IsKind(SyntaxKind.StaticKeyword))) continue;
            if (IsMutableContainer(property.Type)) return true;
        }

        return false;
    }

    private static bool IsMutableContainer(TypeSyntax type)
    {
        if (type is ArrayTypeSyntax) return true;
        var name = TypeLeaf(type);
        return MutableContainerNames.Contains(name);
    }

    private void CheckOperationalValues()
    {
        var declarations = new List<(string Owner, string Name, string Literal, string Path, int Line, Unit Unit)>();
        var methods = MethodParameters();
        var constructors = ConstructorParameters();

        foreach (var (path, syntax) in _syntax.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (!ValueRoles.Contains(unit.Role)) continue;
            var lines = SourceLines(path);

            foreach (var local in syntax.DescendantNodes().OfType<LocalDeclarationStatementSyntax>())
            {
                foreach (var variable in local.Declaration.Variables)
                {
                    var name = variable.Identifier.ValueText;
                    if (variable.Initializer is null || !ContainsOperational(name)
                        || !IsLiteral(variable.Initializer.Value)) continue;
                    if (local.Modifiers.Any(token => token.IsKind(SyntaxKind.ConstKeyword)))
                        CollectValue(unit, path, name, variable.Initializer.Value, LineOf(variable), lines, declarations);
                    else
                        AddValueFinding(unit, path, name, LineOf(variable), "mutable",
                            variable.Initializer.Value, lines);
                }
            }

            foreach (var field in syntax.DescendantNodes().OfType<FieldDeclarationSyntax>())
            {
                var immutable = field.Modifiers.Any(token => token.IsKind(SyntaxKind.ConstKeyword)
                    || token.IsKind(SyntaxKind.ReadOnlyKeyword));
                foreach (var variable in field.Declaration.Variables)
                {
                    var name = variable.Identifier.ValueText;
                    if (variable.Initializer is null || !ContainsOperational(name)
                        || !IsLiteral(variable.Initializer.Value)) continue;
                    if (immutable)
                        CollectValue(unit, path, name, variable.Initializer.Value, LineOf(variable), lines, declarations);
                    else
                        AddValueFinding(unit, path, name, LineOf(variable), "mutable",
                            variable.Initializer.Value, lines);
                }
            }

            foreach (var property in syntax.DescendantNodes().OfType<PropertyDeclarationSyntax>())
            {
                if (property.Initializer is null || !ContainsOperational(property.Identifier.ValueText)
                    || !IsLiteral(property.Initializer.Value)) continue;
                var mutable = property.AccessorList?.Accessors.Any(accessor =>
                    accessor.IsKind(SyntaxKind.SetAccessorDeclaration)) == true;
                if (!mutable)
                    CollectValue(unit, path, property.Identifier.ValueText,
                        property.Initializer.Value, LineOf(property), lines, declarations);
                else
                    AddValueFinding(unit, path, property.Identifier.ValueText, LineOf(property),
                        "property", property.Initializer.Value, lines);
            }

            CheckInlineValues(path, unit, syntax, lines, methods, constructors);
        }

        foreach (var group in declarations.GroupBy(item =>
                     (Owner: item.Unit.Module ?? item.Path, Name: NormalizeName(item.Name), item.Literal)))
        {
            var ordered = group.OrderBy(item => item.Path, StringComparer.Ordinal)
                .ThenBy(item => item.Line).ToList();
            if (ordered.Count < 2) continue;
            var first = ordered[0];
            foreach (var duplicate in ordered.Skip(1))
            {
                var lines = SourceLines(duplicate.Path);
                AddValueFinding(duplicate.Unit, duplicate.Path, duplicate.Name, duplicate.Line,
                    "inline", null, lines,
                    $"{duplicate.Unit.Id} declares {duplicate.Name} with the same apparent meaning and literal value as {first.Path}:{first.Line}; confirm semantic identity and one declaration at the highest common owner before consolidating.");
            }
        }
    }

    private void CollectValue(Unit unit, string path, string name, ExpressionSyntax value,
        int line, string[] lines,
        List<(string Owner, string Name, string Literal, string Path, int Line, Unit Unit)> declarations)
    {
        if (ValueCategory(name) != "value")
        {
            AddValueFinding(unit, path, name, line, "inline", value, lines);
            return;
        }
        declarations.Add((unit.Module ?? path, name, LiteralText(value), path, line, unit));
    }

    private void AddValueFinding(Unit unit, string path, string name, int line, string kind,
        ExpressionSyntax? value, string[] lines, string? message = null)
    {
        if (message is null)
        {
            var category = ValueCategory(name);
            if (category == "secret")
                message = $"{unit.Id} declares a secret-looking literal in {name}; resolve it through the secret mechanism and never commit or log the value.";
            else if (category == "configuration")
                message = $"{unit.Id} declares {name} as a source literal; classify it as a stable code-owned constant or as deployment/runtime configuration resolved and validated at a composition boundary.";
            else if (kind == "mutable")
                message = $"{unit.Id} declares the meaningful value {name} mutably; use an immutable constant, readonly field or immutable value object, or document why mutation is genuinely required.";
            else if (kind == "property")
                message = $"{unit.Id} assigns the meaningful value {name} through a mutable property; prefer an immutable declaration or a readonly value object owned by the type.";
            else
                message = $"{unit.Id} embeds a meaningful value in {name}; declare it once as an immutable constant in the owning file or type, or supply it explicitly from the appropriate configuration boundary.";
        }

        var evidence = value is not null ? value.ToString() : SourceLine(lines, line, name);
        Add(A006, message, path, line, evidence, "candidate");
    }

    private static string ValueCategory(string name)
    {
        if (ContainsToken(name, SecretTokens)) return "secret";
        if (ContainsToken(name, ConfigurationTokens)) return "configuration";
        return "value";
    }

    private static bool ContainsOperational(string name) => ContainsToken(name, OperationalTokens);

    private static string NormalizeName(string name) =>
        Regex.Replace(name, "(?<=[a-z0-9])(?=[A-Z])", "_").ToLowerInvariant();

    private static bool IsLiteral(ExpressionSyntax expression) => expression switch
    {
        LiteralExpressionSyntax literal when !literal.IsKind(SyntaxKind.NullLiteralExpression)
            && !literal.IsKind(SyntaxKind.DefaultLiteralExpression) => true,
        InterpolatedStringExpressionSyntax => true,
        PrefixUnaryExpressionSyntax unary when unary.Operand is LiteralExpressionSyntax => true,
        _ => false,
    };

    private Dictionary<string, List<(string Owner, string[] Names)>> MethodParameters()
    {
        var result = new Dictionary<string, List<(string Owner, string[] Names)>>(StringComparer.Ordinal);
        foreach (var (path, syntax) in _syntax.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            foreach (var method in syntax.DescendantNodes().OfType<MethodDeclarationSyntax>())
            {
                var name = method.Identifier.ValueText;
                var owner = method.Ancestors().OfType<TypeDeclarationSyntax>().FirstOrDefault()?.Identifier.ValueText ?? path;
                var names = method.ParameterList.Parameters.Select(parameter => parameter.Identifier.ValueText).ToArray();
                if (!result.TryGetValue(name, out var entries)) result[name] = entries = new();
                if (!entries.Any(entry => entry.Owner == owner && entry.Names.SequenceEqual(names)))
                    entries.Add((owner, names));
            }
        }

        return result;
    }

    private Dictionary<string, List<string[]>> ConstructorParameters()
    {
        var result = new Dictionary<string, List<string[]>>(StringComparer.Ordinal);
        foreach (var (_, syntax) in _syntax.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            foreach (var constructor in syntax.DescendantNodes().OfType<ConstructorDeclarationSyntax>())
            {
                if (constructor.Parent is not TypeDeclarationSyntax owner) continue;
                var names = constructor.ParameterList.Parameters.Select(parameter => parameter.Identifier.ValueText).ToArray();
                if (!result.TryGetValue(owner.Identifier.ValueText, out var entries))
                    result[owner.Identifier.ValueText] = entries = new();
                if (!entries.Any(entry => entry.SequenceEqual(names))) entries.Add(names);
            }
            foreach (var declaration in syntax.DescendantNodes().OfType<TypeDeclarationSyntax>())
            {
                if (declaration.ParameterList is null) continue;
                var names = declaration.ParameterList.Parameters.Select(parameter => parameter.Identifier.ValueText).ToArray();
                if (!result.TryGetValue(declaration.Identifier.ValueText, out var entries))
                    result[declaration.Identifier.ValueText] = entries = new();
                if (!entries.Any(entry => entry.SequenceEqual(names))) entries.Add(names);
            }
        }

        return result;
    }

    private void CheckInlineValues(string path, Unit unit, SyntaxNode syntax, string[] lines,
        Dictionary<string, List<(string Owner, string[] Names)>> methods,
        Dictionary<string, List<string[]>> constructors)
    {
        foreach (var invocation in syntax.DescendantNodes().OfType<InvocationExpressionSyntax>())
        {
            var name = CallName(invocation.Expression);
            if (string.IsNullOrEmpty(name) || !methods.TryGetValue(name, out var candidates)) continue;
            var currentType = invocation.Ancestors().OfType<TypeDeclarationSyntax>().FirstOrDefault();
            var receiverType = invocation.Expression switch
            {
                IdentifierNameSyntax => currentType?.Identifier.ValueText,
                MemberAccessExpressionSyntax member => ResolveReceiverType(member.Expression, invocation, currentType,
                    new HashSet<string>(_types.Keys, StringComparer.Ordinal)),
                _ => null,
            };
            if (string.IsNullOrEmpty(receiverType)) continue;
            var matching = candidates.Where(candidate => candidate.Owner == receiverType).ToList();
            if (matching.Count == 0) continue;
            foreach (var argument in invocation.ArgumentList.Arguments)
            {
                var parameter = argument.NameColon?.Name.Identifier.ValueText;
                if (parameter is null)
                {
                    var index = invocation.ArgumentList.Arguments.IndexOf(argument);
                    var names = matching.Where(candidate => index < candidate.Names.Length)
                        .Select(candidate => candidate.Names[index]).Distinct(StringComparer.Ordinal).ToList();
                    if (names.Count != 1) continue;
                    parameter = names[0];
                }
                if (!ContainsOperational(parameter) || !IsLiteral(argument.Expression)) continue;
                AddValueFinding(unit, path, parameter, LineOf(argument), "inline",
                    argument.Expression, lines);
            }
        }

        foreach (var creation in syntax.DescendantNodes().OfType<ObjectCreationExpressionSyntax>())
        {
            var owner = TypeLeaf(creation.Type);
            if (string.IsNullOrEmpty(owner) || !constructors.TryGetValue(owner, out var candidates)) continue;
            if (creation.ArgumentList is null) continue;
            foreach (var argument in creation.ArgumentList.Arguments)
            {
                var parameter = argument.NameColon?.Name.Identifier.ValueText;
                if (parameter is null)
                {
                    var index = creation.ArgumentList.Arguments.IndexOf(argument);
                    var names = candidates.Where(candidate => index >= 0 && index < candidate.Length)
                        .Select(candidate => candidate[index]).Distinct(StringComparer.Ordinal).ToList();
                    if (names.Count != 1) continue;
                    parameter = names[0];
                }
                if (!ContainsOperational(parameter) || !IsLiteral(argument.Expression)) continue;
                AddValueFinding(unit, path, parameter, LineOf(argument), "inline",
                    argument.Expression, lines);
            }
        }
    }

    private string[] SourceLines(string path) => _sourceLines.TryGetValue(path, out var lines)
        ? lines
        : Array.Empty<string>();

    private static int LineOf(SyntaxNode node) =>
        node.GetLocation().GetLineSpan().StartLinePosition.Line + 1;

    private static string SourceLine(string[] lines, int line, string fallback) =>
        line > 0 && line <= lines.Length ? lines[line - 1].Trim() : fallback;

    private static ParameterListSyntax? ParameterListOf(SyntaxNode node) => node switch
    {
        MethodDeclarationSyntax method => method.ParameterList,
        ConstructorDeclarationSyntax constructor => constructor.ParameterList,
        LocalFunctionStatementSyntax local => local.ParameterList,
        OperatorDeclarationSyntax op => op.ParameterList,
        ConversionOperatorDeclarationSyntax conversion => conversion.ParameterList,
        _ => null,
    };

    private static string? ResolveReceiverType(ExpressionSyntax receiver,
        InvocationExpressionSyntax invocation, TypeDeclarationSyntax? currentType,
        HashSet<string> declaredTypes)
    {
        if (receiver is MemberAccessExpressionSyntax staticType)
        {
            var typeName = CallName(staticType);
            if (declaredTypes.Contains(typeName)) return typeName;
            return null;
        }
        if (receiver is not IdentifierNameSyntax identifier) return null;
        var name = identifier.Identifier.ValueText;
        if (currentType is null) return null;

        foreach (var field in currentType.Members.OfType<FieldDeclarationSyntax>())
        {
            var match = field.Declaration.Variables.FirstOrDefault(variable => variable.Identifier.ValueText == name);
            if (match is not null) return TypeLeaf(field.Declaration.Type);
        }
        foreach (var property in currentType.Members.OfType<PropertyDeclarationSyntax>())
        {
            if (property.Identifier.ValueText == name) return TypeLeaf(property.Type);
        }
        if (currentType is ClassDeclarationSyntax classDeclaration && classDeclaration.ParameterList is not null)
        {
            var parameter = classDeclaration.ParameterList.Parameters.FirstOrDefault(item => item.Identifier.ValueText == name);
            if (parameter is not null) return TypeLeaf(parameter.Type);
        }
        if (currentType is RecordDeclarationSyntax recordDeclaration && recordDeclaration.ParameterList is not null)
        {
            var parameter = recordDeclaration.ParameterList.Parameters.FirstOrDefault(item => item.Identifier.ValueText == name);
            if (parameter is not null) return TypeLeaf(parameter.Type);
        }

        var scope = invocation.Ancestors().FirstOrDefault(node =>
            node is MethodDeclarationSyntax or ConstructorDeclarationSyntax or LocalFunctionStatementSyntax);
        if (scope is null) return null;
        var parameterList = ParameterListOf(scope);
        var scopedParameter = parameterList?.Parameters.FirstOrDefault(item => item.Identifier.ValueText == name);
        if (scopedParameter is not null) return TypeLeaf(scopedParameter.Type);

        var local = scope.DescendantNodes().OfType<VariableDeclaratorSyntax>()
            .Where(item => item.Identifier.ValueText == name && item.SpanStart < invocation.SpanStart)
            .OrderByDescending(item => item.SpanStart).FirstOrDefault();
        if (local?.Parent is VariableDeclarationSyntax declaration)
        {
            if (!declaration.Type.IsVar) return TypeLeaf(declaration.Type);
            return local.Initializer?.Value switch
            {
                ObjectCreationExpressionSyntax creation => TypeLeaf(creation.Type),
                _ => null,
            };
        }
        return null;
    }
    private void CheckCreation(string path, Unit unit, string[] sourceLines,
        Dictionary<string, List<(string[] Names, bool HasParams)>> constructors, string typeName,
        SeparatedSyntaxList<ArgumentSyntax>? arguments)
    {
        if (string.IsNullOrEmpty(typeName) || arguments is null || !constructors.TryGetValue(typeName, out var signatures)) return;
        var unlabeled = new List<string>();
        var firstLine = 0;
        for (var index = 0; index < arguments.Value.Count; index++)
        {
            var argument = arguments.Value[index];
            if (argument.NameColon is not null) continue;
            var viable = signatures.Where(signature => index < signature.Names.Length ||
                signature.HasParams && signature.Names.Length > 0).ToList();
            if (viable.Count == 0) continue;
            if (viable.All(signature => signature.HasParams && index >= signature.Names.Length - 1))
            {
                var paramsLabels = viable.Where(signature => signature.Names.Length > 0)
                    .Select(signature => signature.Names[^1]).Distinct(StringComparer.Ordinal).ToList();
                var paramsName = paramsLabels.Count == 1 ? paramsLabels[0] : "the declared params parameter";
                var expanded = arguments.Value.Skip(index).Select(item => item.Expression.ToString()).ToList();
                unlabeled.Add(paramsName + ": new[] { " + string.Join(", ", expanded) + " }");
                break;
            }
            var labels = viable.Where(signature => index < signature.Names.Length)
                .Select(signature => signature.Names[index]).Distinct(StringComparer.Ordinal).ToList();
            var hint = labels.Count == 1 ? labels[0] : "the declared parameter";
            unlabeled.Add(hint + ": " + argument.Expression);
            if (firstLine == 0)
                firstLine = argument.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
        }
        if (unlabeled.Count > 0)
        {
            var line = firstLine > 0 ? firstLine : arguments.Value[0].GetLocation().GetLineSpan().StartLinePosition.Line + 1;
            var evidence = line > 0 && line <= sourceLines.Length ? sourceLines[line - 1].Trim() : string.Join(", ", unlabeled);
            Add(D017, $"{unit.Id} constructs {typeName} with unlabeled arguments; label every value: " +
                string.Join(", ", unlabeled) + ".",
                path, line, evidence);
        }
    }
    private void CheckStatics()
    {
        var declarations = new Dictionary<string, (Unit Unit, string Path, int Line)>(StringComparer.Ordinal);
        foreach (var (path, text) in _files.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (unit.Role is not ("implementation" or "shared-kernel")) continue;
            foreach (Match match in InternalStatic.Matches(text))
            {
                declarations[match.Groups[1].Value] = (unit, path, LineOf(text, match.Value));
            }
        }

        var used = new HashSet<string>(StringComparer.Ordinal);
        foreach (var (path, text) in _files.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            foreach (var (name, declaration) in declarations)
            {
                if (declaration.Unit.Module == unit.Module) continue;
                if (unit.Role is "host" or "tooling" or "test") continue;
                if (used.Contains(name)) continue;
                if (!Regex.IsMatch(text, $@"\b{Regex.Escape(name)}\b")) continue;
                used.Add(name);
                Add(A003, $"{unit.Id} imports and may mutate the static state {name} owned by {declaration.Unit.Id}.", declaration.Path, declaration.Line, name);
            }
        }
    }

    private void ApplyWaivers()
    {
        if (string.IsNullOrWhiteSpace(_cfg.Waivers)) return;

        var path = Path.Combine(_root, _cfg.Waivers);
        if (!File.Exists(path))
        {
            Add(G001, $"waivers file is missing: {_cfg.Waivers}", _cfg.Waivers, 1, string.Empty);
            return;
        }

        WaiverDocument document;
        try
        {
            document = JsonSerializer.Deserialize<WaiverDocument>(File.ReadAllText(path), JsonOptions()) ?? new WaiverDocument();
        }
        catch (JsonException)
        {
            Add(G001, $"waivers file is invalid JSON: {_cfg.Waivers}", _cfg.Waivers, 1, string.Empty);
            return;
        }

        var active = new List<Waiver>();
        for (var index = 0; index < document.Waivers.Count; index++)
        {
            var waiver = document.Waivers[index];
            var missing = new List<string>();
            if (string.IsNullOrWhiteSpace(waiver.Rule)) missing.Add("rule");
            if (string.IsNullOrWhiteSpace(waiver.Scope)) missing.Add("scope");
            if (string.IsNullOrWhiteSpace(waiver.Owner)) missing.Add("owner");
            if (string.IsNullOrWhiteSpace(waiver.Reason)) missing.Add("reason");
            if (string.IsNullOrWhiteSpace(waiver.Expires)) missing.Add("expires");
            if (string.IsNullOrWhiteSpace(waiver.ReviewedOn)) missing.Add("reviewedOn");

            if (missing.Count > 0)
            {
                Add(G001, $"Waiver for {waiver.Rule ?? "?"} is missing: {string.Join(", ", missing)}.", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            if (!Catalog.ContainsKey(waiver.Rule!))
            {
                Add(G001, $"Waiver names an unknown rule: {waiver.Rule}.", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            if (waiver.Owner!.Trim().Equals("unassigned", StringComparison.OrdinalIgnoreCase))
            {
                Add(G001, $"Waiver for {waiver.Rule} is owned by 'unassigned'; an unowned exception is not an accepted exception.", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            var globProblem = waiver.Scope!.StartsWith("path:", StringComparison.Ordinal)
                ? WaiverGlobProblem(waiver.Scope[5..]) : null;
            if (globProblem is not null)
            {
                Add(G001, $"Waiver for {waiver.Rule} has an invalid path scope: {globProblem}.", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            if (!DateOnly.TryParseExact(waiver.Expires, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var expiry))
            {
                Add(G001, $"Waiver expiry is not a strict ISO date (YYYY-MM-DD): {waiver.Expires}.", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            if (!DateOnly.TryParseExact(waiver.ReviewedOn, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var reviewed))
            {
                Add(G001, $"Waiver reviewedOn is not a strict ISO date (YYYY-MM-DD): {waiver.ReviewedOn}.", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            var today = DateOnly.FromDateTime(DateTime.UtcNow);
            if (reviewed > today)
            {
                Add(G001, $"Waiver for {waiver.Rule} was reviewed in the future: {waiver.ReviewedOn}.", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            if (reviewed > expiry)
            {
                Add(G001, $"Waiver for {waiver.Rule} was reviewed after it expires: {waiver.ReviewedOn} > {waiver.Expires}.", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            if (expiry < today)
            {
                Add(G002, $"Waiver for {waiver.Rule} expired on {waiver.Expires} (owner: {waiver.Owner}).", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            if (string.IsNullOrWhiteSpace(waiver.Fingerprint))
            {
                Add(G001, $"Waiver for {waiver.Rule} has no finding fingerprint; a broad waiver can hide future findings.", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            if (!WaiverFingerprint.IsMatch(waiver.Fingerprint.Trim()))
            {
                Add(G001, $"Waiver for {waiver.Rule} has a malformed fingerprint; expected sha256:<64 lowercase hex>.", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            waiver.Fingerprint = waiver.Fingerprint.Trim();
            active.Add(waiver);
        }

        if (active.Count == 0) return;

        _findings.RemoveAll(finding =>
        {
            // Source findings resolve through the classified file map. Findings on a project
            // file (project-reference and package rules) have no entry there, so they resolve
            // to their owning unit by its declared paths; otherwise a unit-scoped waiver could
            // never cover them.
            var unit = _fileUnits.TryGetValue(finding.Path, out var mapped)
                ? mapped
                : UnitForPath(finding.Path, string.Empty);
            return active.Any(waiver => waiver.Rule == finding.Rule
                && waiver.Fingerprint == finding.Fingerprint
                && ((unit is not null
                        && (waiver.Scope == "unit:" + unit.Id
                            || waiver.Scope == "module:" + unit.Module))
                    || (waiver.Scope!.StartsWith("path:", StringComparison.Ordinal)
                        && WaiverGlobMatch(waiver.Scope[5..], finding.Path))));
        });
    }

    private void Add(string rule, string message, string path, int line, string evidence,
        string? classification = null)
    {
        if (!Catalog.TryGetValue(rule, out var entry)) return;
        if (Rank[entry.Level] > Rank[_level]) return;
        var trimmed = evidence.Length > 200 ? evidence[..200] : evidence;
        _findings.Add(new Finding(rule, entry.Severity, message, path, Math.Max(line, 1), trimmed,
            FingerprintFor(rule, path, trimmed), classification));
    }

    private static string FingerprintFor(string rule, string path, string evidence)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes($"{rule}\0{path}\0{evidence}"));
        return "sha256:" + Convert.ToHexString(bytes).ToLowerInvariant();
    }

    private static string? WaiverGlobProblem(string pattern)
    {
        if (pattern.Length == 0) return "the pattern is empty";
        if (pattern != pattern.Trim()) return "the pattern has leading or trailing whitespace";
        if (pattern.Contains('\\')) return "use forward slashes";
        if (pattern.StartsWith("/", StringComparison.Ordinal) ||
            pattern.EndsWith("/", StringComparison.Ordinal))
            return "the pattern must be relative and must not end with a slash";
        if (pattern.Contains("//", StringComparison.Ordinal)) return "the pattern contains an empty segment";
        if (pattern.Split('/').Any(part => part is "" or "." or ".."))
            return "the pattern must not contain empty, '.' or '..' segments";
        for (var index = 0; index < pattern.Length; index++)
        {
            if (pattern[index] != '*' || index + 1 >= pattern.Length || pattern[index + 1] != '*') continue;
            var before = index == 0 || pattern[index - 1] == '/';
            var after = index + 2 == pattern.Length || pattern[index + 2] == '/';
            if (!before || !after) return "'**' must be a whole path segment";
            index++;
        }

        return null;
    }

    private static bool WaiverGlobMatch(string pattern, string value)
    {
        if (WaiverGlobProblem(pattern) is not null) return false;
        var regex = new StringBuilder("^");
        for (var index = 0; index < pattern.Length; index++)
        {
            var character = pattern[index];
            if (character == '*')
            {
                if (index + 1 < pattern.Length && pattern[index + 1] == '*')
                {
                    index++;
                    if (index + 1 < pattern.Length && pattern[index + 1] == '/')
                    {
                        index++;
                        regex.Append("(?:[^/]+/)*");
                    }
                    else
                    {
                        regex.Append(".*");
                    }
                }
                else
                {
                    regex.Append("[^/]*");
                }
            }
            else if (character == '?')
            {
                regex.Append("[^/]");
            }
            else
            {
                regex.Append(Regex.Escape(character.ToString()));
            }
        }

        regex.Append('$');
        return Regex.IsMatch(value, regex.ToString());
    }

    private static bool GlobMatch(string pattern, string value)
    {
        // Path globs, not regular expressions: **/ matches zero or more
        // directories (so src/**/*.cs also matches src/Foo.cs), * does not
        // cross a separator, and ? matches one non-separator character.
        var regex = new StringBuilder("^");
        for (var index = 0; index < pattern.Length; index++)
        {
            var character = pattern[index];
            if (character == '*')
            {
                if (index + 1 < pattern.Length && pattern[index + 1] == '*')
                {
                    index++;
                    if (index + 1 < pattern.Length && pattern[index + 1] == '/')
                    {
                        index++;
                        regex.Append("(?:.*/)?");
                    }
                    else
                    {
                        regex.Append(".*");
                    }
                }
                else
                {
                    regex.Append("[^/]*");
                }
            }
            else if (character == '?')
            {
                regex.Append("[^/]");
            }
            else
            {
                regex.Append(Regex.Escape(character.ToString()));
            }
        }

        regex.Append('$');
        return Regex.IsMatch(value, regex.ToString());
    }

    private Unit? UnitById(string id) => _cfg.Units.FirstOrDefault(u => u.Id == id);

    private static int LineOf(string text, string fragment)
    {
        var index = text.IndexOf(fragment, StringComparison.Ordinal);
        if (index < 0) return 1;
        var line = 1;
        for (var i = 0; i < index; i++)
        {
            if (text[i] == '\n') line++;
        }

        return line;
    }

    private string Relative(string full)
    {
        var rel = Path.GetRelativePath(_root, full);
        return rel.Replace('\\', '/');
    }

    private List<Finding> Dedupe()
    {
        var seen = new HashSet<string>(StringComparer.Ordinal);
        var output = new List<Finding>();
        foreach (var finding in _findings
                     .OrderBy(f => f.Path, StringComparer.Ordinal)
                     .ThenBy(f => f.Line)
                     .ThenBy(f => f.Rule, StringComparer.Ordinal))
        {
            var key = $"{finding.Rule}|{finding.Path}|{finding.Line}";
            if (seen.Add(key)) output.Add(finding);
        }

        return output;
    }

    public static JsonSerializerOptions JsonOptions() => new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };
}

internal static class Program
{
    private static int Main(string[] args)
    {
        string? root = null;
        string? config = null;
        var format = "text";
        string? level = null;
        var verify = false;
        string? baselinePath = null;

        for (var i = 0; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--root":
                    root = args[++i];
                    break;
                case "--config":
                    config = args[++i];
                    break;
                case "--format":
                    format = args[++i];
                    break;
                case "--level":
                    level = args[++i];
                    break;
                case "--verify":
                    verify = true;
                    break;
                case "--baseline":
                    baselinePath = args[++i];
                    break;
                default:
                    Console.Error.WriteLine($"acima: unknown argument {args[i]}");
                    return 2;
            }
        }

        var rootPath = Path.GetFullPath(root ?? ".");
        if (verify) return Verify(rootPath);

        try
        {
            var cfg = Load(rootPath, config ?? "acima.config.json");
            var effective = (level ?? cfg.Level).ToUpperInvariant();
            if (!new[] { "L1", "L2", "L3" }.Contains(effective, StringComparer.Ordinal))
            {
                Console.Error.WriteLine($"acima: unknown level {effective}; expected L1, L2 or L3");
                return 2;
            }
            var enforcer = new Enforcer(rootPath, cfg, effective, config ?? "acima.config.json");
            var findings = enforcer.Run();
            var baseline = baselinePath is null
                ? null
                : LoadBaseline(Path.IsPathRooted(baselinePath) ? baselinePath : Path.Combine(rootPath, baselinePath));
            Print(findings, format, cfg.Standard, effective, enforcer.SourceFiles, cfg, enforcer.ClassifiedFindings, baseline);
            return findings.Any(f => f.Severity == "error" && (baseline is null || !baseline.Contains(f.Fingerprint))) ? 1 : 0;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException)
        {
            Console.Error.WriteLine($"acima: cannot read config {config ?? "acima.config.json"}: {error.Message}");
            return 2;
        }
    }

    private static HashSet<string> LoadBaseline(string path)
    {
        var set = new HashSet<string>(StringComparer.Ordinal);
        using var document = JsonDocument.Parse(File.ReadAllText(path));
        foreach (var property in document.RootElement.EnumerateObject())
        {
            var name = property.Name.ToLowerInvariant();
            if (name == "fingerprints")
            {
                foreach (var entry in property.Value.EnumerateArray())
                {
                    if (entry.GetString() is { Length: > 0 } value) set.Add(value);
                }
            }
            else if (name == "findings")
            {
                foreach (var entry in property.Value.EnumerateArray())
                {
                    foreach (var field in entry.EnumerateObject())
                    {
                        if (field.Name.Equals("fingerprint", StringComparison.OrdinalIgnoreCase)
                            && field.Value.GetString() is { Length: > 0 } value)
                        {
                            set.Add(value);
                        }
                    }
                }
            }
        }

        return set;
    }

    private static int Verify(string root)
    {
        try
        {
            var good = new Enforcer(root, Load(root, "acima.config.json"), "L3", "acima.config.json").Run();
            if (good.Count > 0)
            {
                Console.Error.WriteLine("acima: the production tree is not clean");
                Print(good, "text", "1.0.0", "L3");
                return 1;
            }

            var gallery = new Enforcer(root, Load(root, "acima.gallery.config.json"), "L3", "acima.gallery.config.json").Run();
            var expectedPath = Path.Combine(root, "violations", "expected.json");
            var expected = JsonSerializer.Deserialize<Dictionary<string, List<string>>>(File.ReadAllText(expectedPath))
                           ?? new Dictionary<string, List<string>>();

            var actual = gallery
                .GroupBy(f => f.Rule, StringComparer.Ordinal)
                .ToDictionary(
                    g => g.Key,
                    g => g.Select(f => f.Path).Distinct().OrderBy(p => p, StringComparer.Ordinal).ToList(),
                    StringComparer.Ordinal);

            var rules = expected.Keys.Union(actual.Keys, StringComparer.Ordinal).OrderBy(k => k, StringComparer.Ordinal);
            var drifted = false;
            foreach (var rule in rules)
            {
                expected.TryGetValue(rule, out var want);
                actual.TryGetValue(rule, out var got);
                want ??= new List<string>();
                got ??= new List<string>();
                if (want.SequenceEqual(got, StringComparer.Ordinal)) continue;
                drifted = true;
                Console.Error.WriteLine($"{rule}: expected [{string.Join(", ", want)}], got [{string.Join(", ", got)}]");
            }

            if (drifted) return 1;

            var findings = gallery.Count;
            Console.WriteLine($"ok: clean tree, {actual.Count} rules / {findings} findings in the gallery");
            return 0;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException)
        {
            Console.Error.WriteLine($"acima: verify failed: {error.Message}");
            return 2;
        }
    }

    private static Config Load(string root, string name)
    {
        var path = Path.Combine(root, name);
        var cfg = JsonSerializer.Deserialize<Config>(File.ReadAllText(path), Enforcer.JsonOptions());
        return cfg ?? throw new JsonException($"config {name} is empty");
    }

    private static void Print(IReadOnlyList<Finding> findings, string format, string standard, string level,
        int sourceFiles = 0, Config? cfg = null, IReadOnlyList<Classified>? classified = null, HashSet<string>? baseline = null)
    {
        if (format == "json")
        {
            var notExecuted = Enforcer.NotExecutedFor(cfg);
            var execution = Enforcer.CatalogRules.OrderBy(pair => pair.Key, StringComparer.Ordinal)
                .ToDictionary(
                    pair => pair.Key,
                    pair => (object)(notExecuted.TryGetValue(pair.Key, out var reason)
                        ? new { executed = false, reason }
                        : new { executed = true }));
            object? profileSummary = cfg?.Profile is null ? null : new
            {
                kind = cfg.Profile.Kind,
                owner = cfg.Profile.Owner,
                justification = cfg.Profile.Justification,
                publicApi = cfg.Profile.PublicApi,
                intentionalAdapters = cfg.Profile.IntentionalAdapters?.Count ?? 0,
            };
            var payload = new
            {
                standard,
                level,
                sourceFiles,
                newFindings = baseline is null ? findings.Count : findings.Count(f => !baseline.Contains(f.Fingerprint)),
                knownFindings = baseline is null ? 0 : findings.Count(f => baseline.Contains(f.Fingerprint)),
                profile = profileSummary,
                execution,
                classified = (classified ?? Array.Empty<Classified>()).Select(c => new
                {
                    rule = c.Rule,
                    path = c.Path,
                    line = c.Line,
                    evidence = c.Evidence,
                    classification = c.Classification,
                    declaredBy = c.DeclaredBy,
                    target = c.Target,
                    owner = c.Owner,
                    reason = c.Reason,
                }),
                findings = findings.Select(f => new
                {
                    rule = f.Rule,
                    severity = f.Severity,
                    message = f.Message,
                    path = f.Path,
                    line = f.Line,
                    evidence = f.Evidence,
                    fingerprint = f.Fingerprint,
                    classification = f.Classification,
                    status = baseline is null ? "unclassified" : (baseline.Contains(f.Fingerprint) ? "pre-existing" : "new"),
                }),
            };
            Console.WriteLine(JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
            return;
        }

        foreach (var finding in findings)
        {
            var prefix = baseline is null ? string.Empty : (baseline.Contains(finding.Fingerprint) ? "KNOWN " : "NEW   ");
            Console.WriteLine($"{prefix}{finding.Rule}  {finding.Severity,-7} {finding.Message}");
            Console.WriteLine($"  {finding.Path}:{finding.Line}");
        }

        if (classified is { Count: > 0 })
        {
            Console.WriteLine($"\n{classified.Count} classified finding(s) (declared public API or intentional adapters)");
        }

        var errors = findings.Count(f => f.Severity == "error");
        Console.WriteLine($"\n{findings.Count} finding(s), {errors} error(s) at level {level}");

        if (baseline is not null)
        {
            var known = findings.Count(f => baseline.Contains(f.Fingerprint));
            Console.WriteLine($"  {findings.Count - known} new, {known} pre-existing (baseline applied)");
        }
    }
}
