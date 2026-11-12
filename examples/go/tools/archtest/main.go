// Command archtest is the ACIMA reference enforcer for Go.
//
//	archtest --root . --config acima.config.json --format json
//
// It reads source text and the import graph; it never builds or runs the product code.
// Exit codes: 0 clean, 1 unwaived errors, 2 tool failure.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"
)

type unit struct {
	ID     string   `json:"id"`
	Module string   `json:"module"`
	Role   string   `json:"role"`
	Paths  []string `json:"paths"`
}

type config struct {
	Standard     string   `json:"standard"`
	Language     string   `json:"language"`
	Level        string   `json:"level"`
	ModulePath   string   `json:"modulePath"`
	Units        []unit   `json:"units"`
	SharedKernel string   `json:"sharedKernel"`
	Exclude      []string `json:"exclude"`
	Waivers      string   `json:"waivers"`
}

type finding struct {
	Rule        string `json:"rule"`
	Severity    string `json:"severity"`
	Message     string `json:"message"`
	Path        string `json:"path"`
	Line        int    `json:"line"`
	Evidence    string `json:"evidence"`
	Fingerprint string `json:"fingerprint,omitempty"`
}

type wafer struct {
	Rule        string `json:"rule"`
	Scope       string `json:"scope"`
	Owner       string `json:"owner"`
	Reason      string `json:"reason"`
	Expires     string `json:"expires"`
	ReviewedOn  string `json:"reviewedOn"`
	Fingerprint string `json:"fingerprint"`
}

var catalog = map[string][2]string{
	"ACIMA-D001": {"error", "L1"}, "ACIMA-D002": {"error", "L1"}, "ACIMA-D003": {"error", "L1"},
	"ACIMA-D004": {"error", "L1"}, "ACIMA-D005": {"error", "L1"}, "ACIMA-D006": {"error", "L1"},
	"ACIMA-D007": {"error", "L1"}, "ACIMA-D008": {"error", "L1"}, "ACIMA-D009": {"error", "L1"},
	"ACIMA-L001": {"error", "L1"}, "ACIMA-L002": {"error", "L1"}, "ACIMA-L003": {"error", "L1"},
	"ACIMA-L004": {"warning", "L1"},
	"ACIMA-C001": {"error", "L2"}, "ACIMA-C002": {"error", "L2"}, "ACIMA-C003": {"error", "L2"},
	"ACIMA-C004": {"error", "L2"}, "ACIMA-C005": {"error", "L2"}, "ACIMA-C006": {"error", "L2"},
	"ACIMA-C007": {"warning", "L2"}, "ACIMA-C008": {"error", "L2"},
	"ACIMA-A001": {"error", "L3"}, "ACIMA-A002": {"warning", "L3"},
	"ACIMA-A003": {"error", "L3"}, "ACIMA-A004": {"warning", "L3"},
	"ACIMA-A005": {"warning", "L3"}, "ACIMA-A006": {"warning", "L3"},
	"ACIMA-G001": {"error", "L1"}, "ACIMA-G002": {"error", "L1"},
	"ACIMA-G003": {"warning", "L2"}, "ACIMA-G004": {"error", "L2"},
	"ACIMA-G005": {"error", "L1"},
	"ACIMA-D010": {"error", "L1"},
	"ACIMA-L005": {"warning", "L1"}, "ACIMA-L006": {"error", "L1"}, "ACIMA-L007": {"warning", "L1"},
	"ACIMA-G006": {"warning", "L1"},
	"ACIMA-D011": {"error", "L1"}, "ACIMA-D012": {"error", "L1"},
	"ACIMA-D013": {"warning", "L1"}, "ACIMA-D014": {"warning", "L1"},
	"ACIMA-D015": {"warning", "L1"}, "ACIMA-D016": {"warning", "L1"}, "ACIMA-D017": {"warning", "L1"},
	"ACIMA-A007": {"warning", "L3"}, "ACIMA-A008": {"warning", "L3"}, "ACIMA-A009": {"warning", "L3"},
	"ACIMA-A010": {"error", "L3"}, "ACIMA-A011": {"error", "L3"},
	"ACIMA-A012": {"error", "L3"}, "ACIMA-A013": {"warning", "L3"},
	"ACIMA-A014": {"error", "L3"}, "ACIMA-A015": {"error", "L3"},
	"ACIMA-N001": {"warning", "L3"}, "ACIMA-N002": {"warning", "L3"}, "ACIMA-N003": {"warning", "L3"},
}

var notExecuted = map[string]string{
    "ACIMA-D017": "Go has no native named-argument call syntax; wrapper objects are not required as a substitute.",
	"ACIMA-C003": "behaviour versus validation is a semantic judgement",
	"ACIMA-C007": "constructor completeness needs symbol and API analysis",
	"ACIMA-L004": "service-locator APIs are framework-specific",
	"ACIMA-A002": "configuration APIs differ per ecosystem",
	"ACIMA-A004": "version-lock coupling is visible only across published packages",
	"ACIMA-G004": "an API baseline needs a per-language surface format",
	"ACIMA-D010": "third-party tier rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-L005": "third-party tier rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-L006": "third-party tier rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-L007": "third-party tier rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-G006": "manifest package governance is implemented by the python and typescript enforcers in this revision",
	"ACIMA-D011": "explicit-input rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-D012": "explicit-input rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-A005": "value and configuration rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-A006": "value and configuration rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-D013": "composition rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-D014": "composition rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-D015": "functional capture rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-D016": "functional capture rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-A007": "lifecycle rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-A008": "lifecycle rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-A009": "lifecycle rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-N001": "naming rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-N002": "naming rules are implemented by the python and typescript enforcers in this revision",
	"ACIMA-N003": "semantic naming quality needs human review",
	"ACIMA-C008": "business behavior visibility is a semantic contract review",
	"ACIMA-A010": "effect ownership and commit boundaries require application and operational review",
	"ACIMA-A011": "effect semantics require contract and API review",
	"ACIMA-A012": "outcome truthfulness requires failure, retry and cancellation evidence",
	"ACIMA-A013": "critical-effect evidence requires audit and telemetry inspection",
	"ACIMA-A014": "whether telemetry observes or alters business behaviour needs review",
	"ACIMA-A015": "consistency ownership and guarantees need design review",
}

var rank = map[string]int{"L1": 1, "L2": 2, "L3": 3}

var (
	persistence  = []string{"database/sql", "gorm.io/", "github.com/jmoiron/sqlx", "github.com/jackc/pgx"}
	framework    = []string{"net/http", "github.com/gin-gonic/gin", "github.com/labstack/echo", "github.com/go-chi/chi"}
	ambient      = []*regexp.Regexp{regexp.MustCompile(`time\.Now\(`), regexp.MustCompile(`rand\.Read\(`), regexp.MustCompile(`uuid\.New`), regexp.MustCompile(`time\.Since\(`)}
	sqlTable     = regexp.MustCompile(`(?i)\b(?:from|into|update|join)\s+([a-z][a-z0-9_]*)`)
	doubleQuoted = regexp.MustCompile("\"([^\"]*)\"")
	rawQuoted    = regexp.MustCompile("`([^`]*)`")
	importLine   = regexp.MustCompile(`^(?:([\w.]+)\s+)?"([^"]+)"$`)
	singleImport = regexp.MustCompile(`^import\s+(?:([\w.]+)\s+)?"([^"]+)"$`)
	exportedType = regexp.MustCompile(`(?m)^type\s+([A-Z]\w*)\s+(?:struct|interface|string|int|int64|bool)\b`)
	fieldLine    = regexp.MustCompile(`^\s*([A-Z]\w*)\s+([\[\]\*\w.]+)`)
	pointerRecv  = regexp.MustCompile(`(?m)^func\s+\(\s*\w+\s+\*([A-Z]\w*)\s*\)`)
	structBlock  = regexp.MustCompile(`(?ms)^type\s+([A-Z]\w*)\s+struct\s*\{(.*?)^\}`)
	interfaceAny = regexp.MustCompile(`\binterface\s*\{\s*\}|\bany\b`)
)

type source struct {
	path string
	unit *unit
	text string
}

type edge struct {
	from, to string
	line     int
	evidence string
}

func main() {
	root := flag.String("root", ".", "repository root")
	configPath := flag.String("config", "acima.config.json", "config file")
	format := flag.String("format", "text", "text or json")
	levelFlag := flag.String("level", "", "override conformance level")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fatal(err)
	}
	raw, err := os.ReadFile(filepath.Join(absRoot, *configPath))
	if err != nil {
		fatal(fmt.Errorf("cannot read config %s: %w", *configPath, err))
	}
	var cfg config
	if err := json.Unmarshal(raw, &cfg); err != nil {
		fatal(fmt.Errorf("cannot parse config %s: %w", *configPath, err))
	}
	level := strings.ToUpper(cfg.Level)
	if *levelFlag != "" {
		level = strings.ToUpper(*levelFlag)
	}
	if rank[level] == 0 {
		fatal(fmt.Errorf("unknown level %q; expected L1, L2 or L3", level))
	}

	files := map[string]*source{}
	walk(absRoot, absRoot, cfg.Exclude, files)
	sourceFiles := len(files)

	findings := []finding{}
	add := func(rule, message, path string, line int, evidence string) {
		if rank[catalog[rule][1]] > rank[level] {
			return
		}
		if line < 1 {
			line = 1
		}
		if len(evidence) > 200 {
			evidence = evidence[:200]
		}
		findings = append(findings, finding{Rule: rule, Severity: catalog[rule][0], Message: message, Path: path, Line: line, Evidence: evidence, Fingerprint: fingerprint(rule, path, evidence)})
	}

	for _, file := range files {
		declared := unitByPath(file.path, cfg.Units)
		file.unit = unitFor(file.path, file.text, cfg.Units)
		if declared != nil && file.unit != nil && declared.ID != file.unit.ID {
			add("ACIMA-G005", fmt.Sprintf("Role override changes %s from %s to %s.", file.path, declared.ID, file.unit.ID), file.path, 1, "acima-unit override")
		}
		if file.unit == nil {
			add("ACIMA-G005", fmt.Sprintf("Source file is not part of any declared unit: %s", file.path), file.path, 1, "")
		}
	}
	for _, u := range cfg.Units {
		for _, p := range u.Paths {
			if excluded(p, cfg.Exclude) {
				add("ACIMA-G005", fmt.Sprintf("Declared unit %s excludes its own source: %s.", u.ID, p), p, 1, "exclude overrides unit mapping")
			}
		}
	}

	edges := []edge{}
	byDir := map[string]*source{}
	paths := sortedKeys(files)
	for _, path := range paths {
		byDir[filepath.ToSlash(filepath.Dir(path))] = files[path]
	}

	for _, path := range paths {
		file := files[path]
		if file.unit == nil {
			continue
		}
		for _, im := range importsOf(file.text) {
			targetDir, internal := resolve(im.spec, cfg.ModulePath)
			if !internal {
				if file.unit.Role == "contracts" && thirdParty(im.spec) {
					add("ACIMA-D004", fmt.Sprintf("contracts unit %s depends on third-party package: %s", file.unit.ID, im.spec), path, im.line, im.evidence)
				} else if file.unit.Role == "shared-kernel" && thirdParty(im.spec) {
					add("ACIMA-D007", fmt.Sprintf("shared kernel depends on a third-party package: %s", im.spec), path, im.line, im.evidence)
				}
				continue
			}
			target := byDir[targetDir]
			if target == nil || target.unit == nil {
				continue
			}
			edges = append(edges, edge{path, target.path, im.line, im.evidence})
			checkEdge(add, file, target, im, path)
		}
	}

	checkCycles(add, edges, files)
	checkTransitive(add, edges, files, cfg)
	checkContracts(add, files)
	checkLayering(add, files, cfg)
	checkSQL(add, files, cfg)
	checkStatics(add, files, edges, byDir)
	waiverFindings := []finding{}
	addWaiver := func(rule, message, path string, line int, evidence string) {
		if rank[catalog[rule][1]] > rank[level] {
			return
		}
		if line < 1 {
			line = 1
		}
		if len(evidence) > 200 {
			evidence = evidence[:200]
		}
		waiverFindings = append(waiverFindings, finding{Rule: rule, Severity: catalog[rule][0], Message: message, Path: path, Line: line, Evidence: evidence, Fingerprint: fingerprint(rule, path, evidence)})
	}
	findings = applyWaivers(addWaiver, findings, files, cfg, absRoot)
	findings = append(findings, waiverFindings...)

	findings = dedupe(findings)
	execution := map[string]map[string]any{}
	for rule := range catalog {
		if reason, ok := notExecuted[rule]; ok {
			execution[rule] = map[string]any{"executed": false, "reason": reason}
		} else {
			execution[rule] = map[string]any{"executed": true}
		}
	}
	if *format == "json" {
		payload := map[string]any{"standard": cfg.Standard, "level": level, "sourceFiles": sourceFiles, "execution": execution, "findings": findings}
		encoded, _ := json.MarshalIndent(payload, "", "  ")
		fmt.Println(string(encoded))
	} else {
		for _, f := range findings {
			fmt.Printf("%s  %-7s %s\n  %s:%d\n", f.Rule, f.Severity, f.Message, f.Path, f.Line)
		}
		errors := 0
		for _, f := range findings {
			if f.Severity == "error" {
				errors++
			}
		}
		fmt.Printf("\n%d finding(s), %d error(s) at level %s\n", len(findings), errors, level)
	}
	for _, f := range findings {
		if f.Severity == "error" {
			os.Exit(1)
		}
	}
}

func fatal(err error) {
	fmt.Fprintf(os.Stderr, "acima: %v\n", err)
	os.Exit(2)
}

func walk(root, dir string, exclude []string, files map[string]*source) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		fatal(err)
	}
	for _, entry := range entries {
		full := filepath.Join(dir, entry.Name())
		rel, _ := filepath.Rel(root, full)
		rel = filepath.ToSlash(rel)
		if excluded(rel+"/", exclude) && entry.IsDir() {
			continue
		}
		if entry.IsDir() {
			walk(root, full, exclude, files)
			continue
		}
		if !strings.HasSuffix(entry.Name(), ".go") || excluded(rel, exclude) {
			continue
		}
		raw, err := os.ReadFile(full)
		if err != nil {
			fatal(err)
		}
		files[rel] = &source{path: rel, text: string(raw)}
	}
}

func excluded(path string, patterns []string) bool {
	trimmed := strings.TrimSuffix(path, "/")
	// The generated ACIMA workspace is not application source.
	if trimmed == "acima" || strings.HasPrefix(trimmed, "acima/") {
		return true
	}
	for _, pattern := range patterns {
		clean := strings.ReplaceAll(strings.ReplaceAll(pattern, "**", ""), "*", "")
		if trimmed == clean || strings.HasPrefix(trimmed, clean+"/") {
			return true
		}
	}
	for _, part := range strings.Split(trimmed, "/") {
		for _, pattern := range patterns {
			if part == strings.TrimSuffix(pattern, "/") {
				return true
			}
		}
	}
	return false
}

func unitByPath(path string, units []unit) *unit {
	var best *unit
	bestLen := -1
	for i := range units {
		for _, prefix := range units[i].Paths {
			clean := strings.TrimSuffix(prefix, "/")
			if (path == clean || strings.HasPrefix(path, clean+"/")) && len(clean) > bestLen {
				best = &units[i]
				bestLen = len(clean)
			}
		}
	}
	return best
}

func unitFor(path, text string, units []unit) *unit {
	head := strings.SplitN(text, "\n", 4)
	head = head[:min(3, len(head))]
	for _, line := range head {
		if idx := strings.Index(line, "acima-unit:"); idx >= 0 {
			token := strings.TrimSpace(line[idx+len("acima-unit:"):])
			token = strings.Fields(token)[0]
			for i := range units {
				if units[i].ID == token {
					return &units[i]
				}
			}
			for i := range units {
				if units[i].Module == token && units[i].Role == "implementation" {
					return &units[i]
				}
			}
			if strings.HasSuffix(token, ".contracts") {
				name := strings.TrimSuffix(token, ".contracts")
				for i := range units {
					if units[i].Module == name && units[i].Role == "contracts" {
						return &units[i]
					}
				}
			}
		}
	}
	return unitByPath(path, units)
}

type importSpec struct {
	spec, evidence string
	line           int
}

func importsOf(text string) []importSpec {
	out := []importSpec{}
	inBlock := false
	for idx, raw := range strings.Split(text, "\n") {
		line := strings.TrimSpace(raw)
		if inBlock {
			if line == ")" {
				inBlock = false
				continue
			}
			if m := importLine.FindStringSubmatch(line); m != nil {
				out = append(out, importSpec{m[2], line, idx + 1})
			}
			continue
		}
		if strings.HasPrefix(line, "import (") {
			inBlock = true
			continue
		}
		if m := singleImport.FindStringSubmatch(line); m != nil {
			out = append(out, importSpec{m[2], line, idx + 1})
		}
	}
	return out
}

func thirdParty(spec string) bool {
	first := strings.Split(spec, "/")[0]
	return strings.Contains(first, ".")
}

func resolve(spec, modulePath string) (string, bool) {
	if modulePath != "" && strings.HasPrefix(spec, modulePath+"/") {
		return strings.TrimPrefix(spec, modulePath+"/"), true
	}
	return "", false
}

func checkEdge(add func(string, string, string, int, string), file, target *source, im importSpec, path string) {
	from, to := file.unit, target.unit
	switch from.Role {
	case "host", "tooling", "test":
		return
	case "shared-kernel":
		if to.Role != "shared-kernel" {
			add("ACIMA-D007", fmt.Sprintf("shared kernel references %s; the kernel must be a leaf.", to.ID), path, im.line, im.evidence)
		}
		return
	case "contracts":
		switch to.Role {
		case "implementation":
			add("ACIMA-D002", fmt.Sprintf("%s references the implementation unit %s.", from.ID, to.ID), path, im.line, im.evidence)
		case "contracts":
			if to.Module != from.Module {
				add("ACIMA-D003", fmt.Sprintf("%s references %s; contracts must be independent.", from.ID, to.ID), path, im.line, im.evidence)
			}
		case "host":
			add("ACIMA-D006", fmt.Sprintf("%s references the host unit; contracts must not know how they are hosted.", from.ID), path, im.line, im.evidence)
		}
		return
	case "implementation":
		if to.Role == "host" {
			add("ACIMA-D006", fmt.Sprintf("%s references the host unit.", from.ID), path, im.line, im.evidence)
		}
		if to.Role == "implementation" && to.Module != from.Module {
			add("ACIMA-D001", fmt.Sprintf("Module %s imports the implementation unit %s (expected %s.contracts).", from.Module, to.ID, to.Module), path, im.line, im.evidence)
			if strings.HasPrefix(strings.TrimSpace(im.evidence), "import .") || strings.Contains(im.spec, "/internal/") || strings.Contains(im.spec, "/impl") {
				add("ACIMA-D009", fmt.Sprintf("%s imports a private identifier from module %s.", from.Module, to.Module), path, im.line, im.evidence)
			}
			if names := exportedTypes(target.text); len(names) > 0 {
				add("ACIMA-L003", fmt.Sprintf("implementation unit %s publishes the public type %s outside the module", to.ID, strings.Join(names, ", ")), target.path, 1, "")
			}
		}
	}
}

func exportedTypes(text string) []string {
	seen := map[string]bool{}
	names := []string{}
	for _, m := range exportedType.FindAllStringSubmatch(text, -1) {
		if !seen[m[1]] {
			seen[m[1]] = true
			names = append(names, m[1])
		}
	}
	sort.Strings(names)
	return names
}

func checkCycles(add func(string, string, string, int, string), edges []edge, files map[string]*source) {
	graph := map[string]map[string]bool{}
	for _, e := range edges {
		a, b := files[e.from].unit, files[e.to].unit
		if a.Module == "" || b.Module == "" || a.Module == b.Module {
			continue
		}
		if graph[a.Module] == nil {
			graph[a.Module] = map[string]bool{}
		}
		graph[a.Module][b.Module] = true
	}
	state := map[string]int{}
	stack := []string{}
	reported := map[string]bool{}
	var visit func(string)
	visit = func(node string) {
		state[node] = 1
		stack = append(stack, node)
		nexts := []string{}
		for n := range graph[node] {
			nexts = append(nexts, n)
		}
		sort.Strings(nexts)
		for _, next := range nexts {
			if state[next] == 0 {
				visit(next)
			} else if state[next] == 1 {
				start := 0
				for i, s := range stack {
					if s == next {
						start = i
					}
				}
				cycle := append(append([]string{}, stack[start:]...), next)
				key := strings.Join(cycle, ">")
				if !reported[key] {
					reported[key] = true
					path := ""
					for _, e := range edges {
						if files[e.from].unit.Module == node && files[e.to].unit.Module == next {
							path = e.from
							break
						}
					}
					add("ACIMA-D005", fmt.Sprintf("Circular module dependency: %s", strings.Join(cycle, " -> ")), path, 1, "")
				}
			}
		}
		stack = stack[:len(stack)-1]
		state[node] = 2
	}
	names := []string{}
	for n := range graph {
		names = append(names, n)
	}
	sort.Strings(names)
	for _, n := range names {
		if state[n] == 0 {
			visit(n)
		}
	}
}

func checkTransitive(add func(string, string, string, int, string), edges []edge, files map[string]*source, cfg config) {
	graph := map[string][]string{}
	for _, e := range edges {
		a, b := files[e.from].unit, files[e.to].unit
		if a == nil || b == nil {
			continue
		}
		graph[a.ID] = append(graph[a.ID], b.ID)
	}
	byID := map[string]unit{}
	for _, u := range cfg.Units {
		byID[u.ID] = u
	}
	seen := map[string]bool{}
	for _, e := range edges {
		a, b := files[e.from].unit, files[e.to].unit
		if a == nil || b == nil || a.Module == b.Module {
			continue
		}
		if a.Role != "contracts" && a.Role != "implementation" {
			continue
		}
		reachable := map[string]bool{b.ID: true}
		queue := []string{b.ID}
		for len(queue) > 0 {
			node := queue[0]
			queue = queue[1:]
			for _, next := range graph[node] {
				if !reachable[next] {
					reachable[next] = true
					queue = append(queue, next)
				}
			}
		}
		ids := []string{}
		for id := range reachable {
			ids = append(ids, id)
		}
		sort.Strings(ids)
		for _, id := range ids {
			target, ok := byID[id]
			if !ok || target.Module == a.Module || target.Role != "implementation" {
				continue
			}
			key := a.ID + ">" + target.ID
			if seen[key] {
				continue
			}
			seen[key] = true
			add("ACIMA-D008", fmt.Sprintf("%s reaches the implementation unit %s transitively through %s.", a.ID, target.ID, b.ID), e.from, e.line, e.evidence)
		}
	}
}

func checkContracts(add func(string, string, string, int, string), files map[string]*source) {
	for _, path := range sortedKeys(files) {
		file := files[path]
		if file.unit == nil || file.unit.Role != "contracts" {
			continue
		}
		for _, pattern := range ambient {
			if m := pattern.FindStringIndex(file.text); m != nil {
				add("ACIMA-C004", fmt.Sprintf("contracts unit %s reads ambient state (%s).", file.unit.ID, pattern.String()), path, lineOf(file.text, m[0]), pattern.String())
			}
		}
		for _, token := range persistence {
			if idx := strings.Index(file.text, token); idx >= 0 {
				add("ACIMA-C005", fmt.Sprintf("contracts unit %s exposes a persistence concern (%s).", file.unit.ID, token), path, lineOf(file.text, idx), token)
			}
		}
		for _, token := range framework {
			if idx := strings.Index(file.text, `"`+token); idx >= 0 {
				add("ACIMA-L002", fmt.Sprintf("contracts unit %s exposes a framework type (%s).", file.unit.ID, token), path, lineOf(file.text, idx), token)
			}
		}
		for _, m := range structBlock.FindAllStringSubmatchIndex(file.text, -1) {
			name := file.text[m[2]:m[3]]
			body := file.text[m[4]:m[5]]
			blockLine := lineOf(file.text, m[0])
			for _, raw := range strings.Split(body, "\n") {
				field := fieldLine.FindStringSubmatch(raw)
				if field == nil {
					continue
				}
				if field[1] == "" || field[1][0] < 'A' || field[1][0] > 'Z' {
					continue
				}
				typ := field[2]
				if strings.HasPrefix(typ, "*") {
					add("ACIMA-C001", fmt.Sprintf("Contract type %s exposes a pointer field (%s); value semantics required.", name, field[1]), path, blockLine, strings.TrimSpace(raw))
				}
				if strings.HasPrefix(typ, "map[") || strings.Contains(typ, "[]") {
					add("ACIMA-C002", fmt.Sprintf("Contract type %s exposes a mutable collection (%s).", name, field[1]), path, blockLine, strings.TrimSpace(raw))
				}
				if interfaceAny.MatchString(typ) {
					add("ACIMA-C006", fmt.Sprintf("Contract type %s has an untyped field (%s).", name, field[1]), path, blockLine, strings.TrimSpace(raw))
				}
			}
			if commentBefore(file.text, m[0], name) == false {
				add("ACIMA-G003", fmt.Sprintf("Contract type %s has no documentation.", name), path, blockLine, "")
			}
		}
		if m := pointerRecv.FindStringSubmatch(file.text); m != nil {
			add("ACIMA-C001", fmt.Sprintf("Contract type %s has a mutating pointer receiver.", m[1]), path, lineOf(file.text, strings.Index(file.text, m[0])), m[0])
		}
	}
}

func fingerprint(rule, path, evidence string) string {
	sum := sha256.Sum256([]byte(rule + "\x00" + path + "\x00" + evidence))
	return "sha256:" + hex.EncodeToString(sum[:])
}

func globMatch(pattern, value string) bool {
	matched, err := filepath.Match(pattern, value)
	return err == nil && matched
}

func commentBefore(text string, index int, name string) bool {
	lines := strings.Split(text[:index], "\n")
	seen := false
	for i := len(lines) - 1; i >= 0; i-- {
		line := strings.TrimSpace(lines[i])
		if line == "" {
			if seen {
				return false
			}
			continue
		}
		if !strings.HasPrefix(line, "//") {
			return false
		}
		seen = true
		if strings.Contains(line, name) || strings.Contains(line, "Package") {
			return true
		}
	}
	return false
}

func checkLayering(add func(string, string, string, int, string), files map[string]*source, cfg config) {
	for _, path := range sortedKeys(files) {
		file := files[path]
		if file.unit == nil || file.unit.Role != "implementation" || strings.Contains(path, "/infrastructure/") {
			continue
		}
		for _, im := range importsOf(file.text) {
			for _, token := range persistence {
				if im.spec != token && !strings.HasPrefix(im.spec, strings.TrimSuffix(token, "/")+"/") {
					continue
				}
				add("ACIMA-L001", fmt.Sprintf("%s imports infrastructure (%s) outside infrastructure/.", file.unit.ID, im.spec), path, im.line, im.evidence)
			}
		}
	}
}

func checkSQL(add func(string, string, string, int, string), files map[string]*source, cfg config) {
	modules := map[string]bool{}
	for _, u := range cfg.Units {
		if u.Module != "" {
			modules[u.Module] = true
		}
	}
	for _, path := range sortedKeys(files) {
		file := files[path]
		if file.unit == nil {
			continue
		}
		for _, re := range []*regexp.Regexp{doubleQuoted, rawQuoted} {
			for _, m := range re.FindAllStringSubmatchIndex(file.text, -1) {
				inner := file.text[m[2]:m[3]]
				for _, table := range sqlTable.FindAllStringSubmatch(inner, -1) {
					prefix := strings.Split(table[1], "_")[0]
					if modules[prefix] && prefix != file.unit.Module {
						add("ACIMA-A001", fmt.Sprintf("%s queries the %s schema (%s); each module owns its own tables.", file.unit.ID, prefix, table[1]), path, lineOf(file.text, m[0]), table[1])
					}
				}
			}
		}
	}
}

func checkStatics(add func(string, string, string, int, string), files map[string]*source, edges []edge, byDir map[string]*source) {
	declared := map[string]*source{}
	staticDecl := regexp.MustCompile(`(?m)^var\s+([A-Za-z_]\w*)\s*=\s*(?:map\[|&)`)
	for _, path := range sortedKeys(files) {
		file := files[path]
		if file.unit == nil || (file.unit.Role != "implementation" && file.unit.Role != "shared-kernel") {
			continue
		}
		for _, m := range staticDecl.FindAllStringSubmatchIndex(file.text, -1) {
			declared[file.text[m[2]:m[3]]] = file
		}
	}
	used := map[string]bool{}
	for _, e := range edges {
		from := files[e.from]
		for name, decl := range declared {
			if decl.unit.Module != from.unit.Module && !used[name] && strings.Contains(from.text, name) {
				used[name] = true
				add("ACIMA-A003", fmt.Sprintf("%s imports and may mutate the static state %s owned by %s.", from.unit.ID, name, decl.unit.ID), decl.path, 1, name)
			}
		}
	}
}

func applyWaivers(add func(string, string, string, int, string), findings []finding, files map[string]*source, cfg config, root string) []finding {
	if cfg.Waivers == "" {
		return findings
	}
	raw, err := os.ReadFile(filepath.Join(root, cfg.Waivers))
	if err != nil {
		add("ACIMA-G001", fmt.Sprintf("waivers file is missing: %s", cfg.Waivers), cfg.Waivers, 1, "")
		return findings
	}
	var doc struct {
		Waivers []wafer `json:"waivers"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		add("ACIMA-G001", fmt.Sprintf("waivers file is invalid JSON: %s", cfg.Waivers), cfg.Waivers, 1, "")
		return findings
	}
	active := []wafer{}
	for i, w := range doc.Waivers {
		missing := []string{}
		for field, value := range map[string]string{"rule": w.Rule, "scope": w.Scope, "owner": w.Owner, "reason": w.Reason, "expires": w.Expires, "reviewedOn": w.ReviewedOn} {
			if strings.TrimSpace(value) == "" {
				missing = append(missing, field)
			}
		}
		sort.Strings(missing)
		if len(missing) > 0 {
			add("ACIMA-G001", fmt.Sprintf("Waiver for %s is missing: %s.", w.Rule, strings.Join(missing, ", ")), cfg.Waivers, i+1, "")
			continue
		}
		if _, ok := catalog[w.Rule]; !ok {
			add("ACIMA-G001", fmt.Sprintf("Waiver names an unknown rule: %s.", w.Rule), cfg.Waivers, i+1, "")
			continue
		}
		expiry, err := parseDate(w.Expires)
		if err != nil {
			add("ACIMA-G001", fmt.Sprintf("Waiver expiry is not an ISO date: %s.", w.Expires), cfg.Waivers, i+1, "")
			continue
		}
		if expiry.Before(now()) {
			add("ACIMA-G002", fmt.Sprintf("Waiver for %s expired on %s (owner: %s).", w.Rule, w.Expires, w.Owner), cfg.Waivers, i+1, "")
			continue
		}
		if strings.TrimSpace(w.Fingerprint) == "" {
			add("ACIMA-G001", fmt.Sprintf("Waiver for %s has no finding fingerprint; a broad waiver can hide future findings.", w.Rule), cfg.Waivers, i+1, "")
			continue
		}
		active = append(active, w)
	}
	kept := []finding{}
	for _, f := range findings {
		unit := files[f.Path]
		waived := false
		if unit != nil && unit.unit != nil {
			for _, w := range active {
				if w.Rule != f.Rule {
					continue
				}
				if w.Fingerprint == "" || w.Fingerprint != f.Fingerprint {
					continue
				}
				if w.Scope == "unit:"+unit.unit.ID || w.Scope == "module:"+unit.unit.Module ||
					(strings.HasPrefix(w.Scope, "path:") && globMatch(w.Scope[5:], f.Path)) {
					waived = true
				}
			}
		}
		if !waived {
			kept = append(kept, f)
		}
	}
	return kept
}

func dedupe(findings []finding) []finding {
	seen := map[string]bool{}
	out := []finding{}
	sort.SliceStable(findings, func(i, j int) bool {
		if findings[i].Path != findings[j].Path {
			return findings[i].Path < findings[j].Path
		}
		if findings[i].Line != findings[j].Line {
			return findings[i].Line < findings[j].Line
		}
		return findings[i].Rule < findings[j].Rule
	})
	for _, f := range findings {
		key := fmt.Sprintf("%s|%s|%d", f.Rule, f.Path, f.Line)
		if !seen[key] {
			seen[key] = true
			out = append(out, f)
		}
	}
	return out
}

func parseDate(value string) (time.Time, error) {
	return time.Parse("2006-01-02", value)
}

func now() time.Time { return time.Now() }

func lineOf(text string, index int) int {
	return strings.Count(text[:index], "\n") + 1
}

func sortedKeys(m map[string]*source) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
