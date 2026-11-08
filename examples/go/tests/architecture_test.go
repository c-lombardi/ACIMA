// Package tests holds the architecture gate. It runs the enforcer over the good tree and
// compares the violation gallery with the documented findings.
package tests

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"sort"
	"testing"
)

type finding struct {
	Rule     string `json:"rule"`
	Severity string `json:"severity"`
	Message  string `json:"message"`
	Path     string `json:"path"`
	Line     int    `json:"line"`
}

type report struct {
	Standard string    `json:"standard"`
	Level    string    `json:"level"`
	Findings []finding `json:"findings"`
}

func runEnforcer(t *testing.T, args ...string) (int, report) {
	t.Helper()
	root, err := filepath.Abs("..")
	if err != nil {
		t.Fatal(err)
	}
	full := append([]string{"run", "./tools/archtest", "--root", root}, args...)
	cmd := exec.Command("go", full...)
	cmd.Dir = root
	output, err := cmd.Output()
	code := 0
	if exit, ok := err.(*exec.ExitError); ok {
		code = exit.ExitCode()
	} else if err != nil {
		t.Fatalf("enforcer failed to run: %v", err)
	}
	var parsed report
	if len(output) == 0 {
		t.Fatalf("enforcer produced no output")
	}
	if err := json.Unmarshal(output, &parsed); err != nil {
		t.Fatalf("enforcer produced no JSON: %v", err)
	}
	return code, parsed
}

func TestProductionCodeHasNoFindings(t *testing.T) {
	code, parsed := runEnforcer(t, "--format", "json")
	if len(parsed.Findings) != 0 {
		t.Fatalf("expected a clean tree, got %v", parsed.Findings)
	}
	if code != 0 {
		t.Fatalf("expected exit 0, got %d", code)
	}
}

func TestGalleryMatchesDocumentedFindings(t *testing.T) {
	_, parsed := runEnforcer(t, "--config", "acima.gallery.config.json", "--format", "json")
	actual := map[string]map[string]bool{}
	for _, f := range parsed.Findings {
		if actual[f.Rule] == nil {
			actual[f.Rule] = map[string]bool{}
		}
		actual[f.Rule][f.Path] = true
	}
	collected := map[string][]string{}
	for rule, paths := range actual {
		for path := range paths {
			collected[rule] = append(collected[rule], path)
		}
		sort.Strings(collected[rule])
	}
	raw, err := os.ReadFile(filepath.Join("..", "violations", "expected.json"))
	if err != nil {
		t.Fatal(err)
	}
	expected := map[string][]string{}
	if err := json.Unmarshal(raw, &expected); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(collected, expected) {
		t.Fatalf("gallery drifted:\nactual:   %v\nexpected: %v", collected, expected)
	}
}

func TestFindingsCarryRequiredFields(t *testing.T) {
	_, parsed := runEnforcer(t, "--config", "acima.gallery.config.json", "--format", "json")
	if len(parsed.Findings) == 0 {
		t.Fatal("a suite that finds nothing proves nothing")
	}
	for _, f := range parsed.Findings {
		if f.Rule == "" || f.Severity == "" || f.Message == "" || f.Path == "" || f.Line < 1 {
			t.Fatalf("incomplete finding: %+v", f)
		}
	}
}
