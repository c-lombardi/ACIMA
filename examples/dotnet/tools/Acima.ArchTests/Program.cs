using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml.Linq;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

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

internal sealed record Finding(string Rule, string Severity, string Message, string Path, int Line, string Evidence, string Fingerprint);

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
        [D011] = "explicit-input rules are implemented by the python and typescript enforcers in this revision",
        [D012] = "explicit-input rules are implemented by the python and typescript enforcers in this revision",
        [A005] = "value and configuration rules are implemented by the python and typescript enforcers in this revision",
        [A006] = "value and configuration rules are implemented by the python and typescript enforcers in this revision",
        [D013] = "composition rules are implemented by the python and typescript enforcers in this revision",
        [D014] = "composition rules are implemented by the python and typescript enforcers in this revision",
        [D015] = "functional capture rules are implemented by the python and typescript enforcers in this revision",
        [D016] = "functional capture rules are implemented by the python and typescript enforcers in this revision",
        [A007] = "lifecycle rules are implemented by the python and typescript enforcers in this revision",
        [A008] = "lifecycle rules are implemented by the python and typescript enforcers in this revision",
        [A009] = "lifecycle rules are implemented by the python and typescript enforcers in this revision",
        [N001] = "naming rules are implemented by the python and typescript enforcers in this revision",
        [N002] = "naming rules are implemented by the python and typescript enforcers in this revision",
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
    private static readonly Regex UsingDirective = new(@"^\s*using\s+(?:static\s+)?([\w\.]+)\s*;", RegexOptions.Multiline | RegexOptions.Compiled);
    private static readonly Regex PublicType = new(@"^\s*public\s+(?:sealed\s+|abstract\s+|readonly\s+|partial\s+|static\s+)*(?:class|record|struct|interface|enum)\s+(\w+)", RegexOptions.Multiline | RegexOptions.Compiled);
    private static readonly Regex InternalType = new(@"^\s*internal\s+(?:sealed\s+|abstract\s+|readonly\s+|partial\s+|static\s+)*(?:class|record|struct|interface)\s+(\w+)", RegexOptions.Multiline | RegexOptions.Compiled);
    private static readonly Regex InternalStatic = new(@"^\s*public\s+static\s+(?!readonly\b)[\w<>,\[\]\.\?]+\s+(\w+)\s*(?:=\s*(?!=)|;)", RegexOptions.Multiline | RegexOptions.Compiled);
    private static readonly Regex StringLiteral = new("\"((?:[^\"\\\\]|\\\\.)*)\"", RegexOptions.Compiled);
    private static readonly Regex SqlTable = new(@"(?i)\b(?:from|into|update|join)\s+([a-z][a-z0-9_]*)", RegexOptions.Compiled);

    private readonly string _root;
    private readonly Config _cfg;
    private readonly string _level;
    private readonly List<Finding> _findings = new();
    private readonly Dictionary<string, string> _files = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Unit> _fileUnits = new(StringComparer.Ordinal);
    private readonly List<string> _projects = new();
    private readonly List<Edge> _edges = new();
    private readonly Dictionary<string, Unit> _namespaceUnits = new(StringComparer.Ordinal);
    private readonly List<Classified> _classified = new();
    private readonly List<PublicApiSurface> _publicApi = new();
    private string? _packagingError;

    public IReadOnlyList<Classified> ClassifiedFindings => _classified;

    public Enforcer(string root, Config config, string level)
    {
        _root = Path.GetFullPath(root);
        _cfg = config;
        _level = Rank.ContainsKey(level) ? level : "L1";
    }

    public IReadOnlyList<Finding> Run()
    {
        Collect();
        Classify();
        ValidateProfile();
        CheckProjects();
        CheckUsings();
        CheckCycles();
        CheckTransitive();
        CheckVisibility();
        CheckContracts();
        CheckLayering();
        CheckSql();
        CheckStatics();
        CheckNamedArguments();
        ApplyWaivers();
        return Dedupe();
    }

    private void Collect()
    {
        Walk(_root);
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

    private void CheckUsings()
    {
        foreach (var (path, text) in _files.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var from = _fileUnits[path];
            foreach (Match match in UsingDirective.Matches(text))
            {
                var ns = match.Groups[1].Value;
                var line = LineOf(text, match.Groups[1].Value);
                var target = ResolveNamespace(ns);

                if (target is not null)
                {
                    if (target.Id == from.Id) continue;
                    _edges.Add(new Edge(from.Id, target.Id, path, line, match.Value.Trim()));
                    CheckEdge(from, target, path, line, match.Value.Trim());
                    continue;
                }

                if (ns.StartsWith("Acima.", StringComparison.Ordinal)) continue;
                if (ns.StartsWith("System", StringComparison.Ordinal)) continue;

                if (from.Role == "contracts")
                {
                    Add(D004, $"contracts unit {from.Id} depends on third-party namespace: {ns}", path, line, match.Value.Trim());
                }
                else if (from.Role == "shared-kernel")
                {
                    Add(D007, $"shared kernel depends on a third-party namespace: {ns}", path, line, match.Value.Trim());
                }
            }
        }
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
        var internals = new Dictionary<string, (Unit Unit, string Path, int Line)>(StringComparer.Ordinal);
        var publics = new Dictionary<string, (Unit Unit, string Path, int Line)>(StringComparer.Ordinal);

        foreach (var (path, text) in _files.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (unit.Role != "implementation") continue;
            foreach (Match match in InternalType.Matches(text))
            {
                internals[match.Groups[1].Value] = (unit, path, LineOf(text, match.Value));
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

            foreach (var (name, declaration) in internals)
            {
                if (declaration.Unit.Module == unit.Module) continue;
                if (!Regex.IsMatch(text, $@"\b{Regex.Escape(name)}\b")) continue;
                if (!ClassifyAdapter(D009, path, LineOf(text, name), name, unit, declaration.Unit, null))
                {
                    Add(D009, $"{unit.Id} references the internal type {name} from module {declaration.Unit.Module}.", path, LineOf(text, name), name);
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
            if (unit.Role != "implementation" || path.Contains("/infrastructure/", StringComparison.Ordinal)) continue;
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

        foreach (var (path, source) in _files.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            var unit = _fileUnits[path];
            if (unit.Role is not ("contracts" or "implementation" or "host" or "adapter" or "port")) continue;
            var tree = CSharpSyntaxTree.ParseText(source, new CSharpParseOptions(LanguageVersion.Latest));
            var syntax = tree.GetRoot();
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

            if (!DateTime.TryParse(waiver.Expires, out var expiry) || expiry.Date < DateTime.UtcNow.Date)
            {
                Add(G002, $"Waiver for {waiver.Rule} expired on {waiver.Expires} (owner: {waiver.Owner}).", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

            if (string.IsNullOrWhiteSpace(waiver.Fingerprint))
            {
                Add(G001, $"Waiver for {waiver.Rule} has no finding fingerprint; a broad waiver can hide future findings.", _cfg.Waivers, index + 1, string.Empty);
                continue;
            }

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
                        && GlobMatch(waiver.Scope[5..], finding.Path))));
        });
    }

    private void Add(string rule, string message, string path, int line, string evidence)
    {
        if (!Catalog.TryGetValue(rule, out var entry)) return;
        if (Rank[entry.Level] > Rank[_level]) return;
        var trimmed = evidence.Length > 200 ? evidence[..200] : evidence;
        _findings.Add(new Finding(rule, entry.Severity, message, path, Math.Max(line, 1), trimmed,
            FingerprintFor(rule, path, trimmed)));
    }

    private static string FingerprintFor(string rule, string path, string evidence)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes($"{rule}\0{path}\0{evidence}"));
        return "sha256:" + Convert.ToHexString(bytes)[..16].ToLowerInvariant();
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
            var enforcer = new Enforcer(rootPath, cfg, effective);
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
            var good = new Enforcer(root, Load(root, "acima.config.json"), "L3").Run();
            if (good.Count > 0)
            {
                Console.Error.WriteLine("acima: the production tree is not clean");
                Print(good, "text", "1.0.0", "L3");
                return 1;
            }

            var gallery = new Enforcer(root, Load(root, "acima.gallery.config.json"), "L3").Run();
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
            var execution = Enforcer.CatalogRules.OrderBy(pair => pair.Key, StringComparer.Ordinal)
                .ToDictionary(
                    pair => pair.Key,
                    pair => (object)(Enforcer.NotExecutedRules.TryGetValue(pair.Key, out var reason)
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
