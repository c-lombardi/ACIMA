using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml.Linq;

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
}

internal sealed class Waiver
{
    public string? Rule { get; set; }
    public string? Scope { get; set; }
    public string? Owner { get; set; }
    public string? Reason { get; set; }
    public string? Expires { get; set; }
    public string? ReviewedOn { get; set; }
}

internal sealed class WaiverDocument
{
    public List<Waiver> Waivers { get; set; } = new();
}

internal sealed record Finding(string Rule, string Severity, string Message, string Path, int Line, string Evidence);

internal sealed record Edge(string From, string To, string Path, int Line, string Evidence);

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
    private const string C001 = "ACIMA-C001";
    private const string C002 = "ACIMA-C002";
    private const string C004 = "ACIMA-C004";
    private const string C005 = "ACIMA-C005";
    private const string C006 = "ACIMA-C006";
    private const string A001 = "ACIMA-A001";
    private const string A003 = "ACIMA-A003";
    private const string G001 = "ACIMA-G001";
    private const string G002 = "ACIMA-G002";
    private const string G003 = "ACIMA-G003";
    private const string G005 = "ACIMA-G005";

    private static readonly Dictionary<string, (string Severity, string Level)> Catalog = new(StringComparer.Ordinal)
    {
        [D001] = ("error", "L1"), [D002] = ("error", "L1"), [D003] = ("error", "L1"),
        [D004] = ("error", "L1"), [D005] = ("error", "L1"), [D006] = ("error", "L1"),
        [D007] = ("error", "L1"), [D008] = ("error", "L1"), [D009] = ("error", "L1"),
        [L001] = ("error", "L1"), [L002] = ("error", "L1"), [L003] = ("error", "L1"),
        [C001] = ("error", "L2"), [C002] = ("error", "L2"), [C004] = ("error", "L2"),
        [C005] = ("error", "L2"), [C006] = ("error", "L2"),
        [A001] = ("error", "L3"), [A003] = ("error", "L3"),
        [G001] = ("error", "L1"), [G002] = ("error", "L1"),
        [G003] = ("warning", "L2"), [G005] = ("error", "L1"),
    };

    private static readonly Dictionary<string, int> Rank = new() { ["L1"] = 1, ["L2"] = 2, ["L3"] = 3 };

    private static readonly Regex PropertySetter = new(@"\{[^{}]*\bset\s*;[^{}]*\}", RegexOptions.Compiled);
    private static readonly Regex PublicField = new(@"^\s*public\s+(?!static\b|const\b|readonly\b)[\w<>,\[\]\.\?]+\s+\w+\s*;", RegexOptions.Multiline | RegexOptions.Compiled);
    private static readonly Regex CollectionMember = new(@"\b(?:List|IList|ICollection|Dictionary|HashSet)<", RegexOptions.Compiled);
    private static readonly Regex Ambient = new(@"\bDateTime(?:Offset)?\.(?:Now|UtcNow)\b|\bGuid\.NewGuid\s*\(|\bnew\s+Random\s*\(|\bEnvironment\.(?:MachineName|TickCount|GetEnvironmentVariable)|TimeProvider\.System", RegexOptions.Compiled);
    private static readonly Regex Persistence = new(@"\bDbContext\b|\bDbSet\s*<|\bIDbConnection\b|\bSqlConnection\b|\bNpgsql\w*\b|\bDapper\b|Microsoft\.EntityFrameworkCore", RegexOptions.Compiled);
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
        CheckProjects();
        CheckUsings();
        CheckCycles();
        CheckTransitive();
        CheckVisibility();
        CheckContracts();
        CheckLayering();
        CheckSql();
        CheckStatics();
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
            var unit = UnitForPath(path, _files[path]);
            if (unit is null)
            {
                Add(G005, $"Source file is not part of any declared unit: {path}", path, 1, string.Empty);
                _files.Remove(path);
                continue;
            }

            _fileUnits[path] = unit;
        }
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
            }
        }
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
                Add(D001, $"Module {from.Module} imports the implementation unit {to.Id} (expected {to.Module}.contracts).", path, line, evidence);
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
                Add(D009, $"{unit.Id} references the internal type {name} from module {declaration.Unit.Module}.", path, LineOf(text, name), name);
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
                Add(L003, $"implementation unit {declaration.Unit.Id} publishes the public type {name} outside the module", declaration.Path, declaration.Line, name);
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
            foreach (Match match in Persistence.Matches(text))
            {
                Add(L001, $"{unit.Id} references infrastructure ({match.Value}) outside infrastructure/.", path, LineOf(text, match.Value), match.Value);
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

            active.Add(waiver);
        }

        if (active.Count == 0) return;

        _findings.RemoveAll(finding =>
        {
            if (!_fileUnits.TryGetValue(finding.Path, out var unit)) return false;
            return active.Any(waiver => waiver.Rule == finding.Rule && waiver.Scope == "unit:" + unit.Id);
        });
    }

    private void Add(string rule, string message, string path, int line, string evidence)
    {
        if (!Catalog.TryGetValue(rule, out var entry)) return;
        if (Rank[entry.Level] > Rank[_level]) return;
        var trimmed = evidence.Length > 200 ? evidence[..200] : evidence;
        _findings.Add(new Finding(rule, entry.Severity, message, path, Math.Max(line, 1), trimmed));
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
            var findings = new Enforcer(rootPath, cfg, effective).Run();
            Print(findings, format, cfg.Standard, effective);
            return findings.Any(f => f.Severity == "error") ? 1 : 0;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException)
        {
            Console.Error.WriteLine($"acima: cannot read config {config ?? "acima.config.json"}: {error.Message}");
            return 2;
        }
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

    private static void Print(IReadOnlyList<Finding> findings, string format, string standard, string level)
    {
        if (format == "json")
        {
            var payload = new
            {
                standard,
                level,
                findings = findings.Select(f => new
                {
                    rule = f.Rule,
                    severity = f.Severity,
                    message = f.Message,
                    path = f.Path,
                    line = f.Line,
                    evidence = f.Evidence,
                }),
            };
            Console.WriteLine(JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
            return;
        }

        foreach (var finding in findings)
        {
            Console.WriteLine($"{finding.Rule}  {finding.Severity,-7} {finding.Message}");
            Console.WriteLine($"  {finding.Path}:{finding.Line}");
        }

        var errors = findings.Count(f => f.Severity == "error");
        Console.WriteLine($"\n{findings.Count} finding(s), {errors} error(s) at level {level}");
    }
}
