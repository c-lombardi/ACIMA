#!/usr/bin/env python3
"""Tests for the service-topology checker.

Builds two temporary repositories: a clean topology and one that violates every
ST item exactly enough to exercise `ACIMA-S001`–`S012`. Run directly:

    python3 conformance/test_topology.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import topology  # noqa: E402


def write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def csproj(root: Path, rel: str, refs: list[str] | None = None,
           packages: list[str] | None = None) -> None:
    lines = ["<Project Sdk=\"Microsoft.NET.Sdk\">", "  <PropertyGroup>",
             "    <TargetFramework>net8.0</TargetFramework>", "  </PropertyGroup>"]
    for ref in refs or []:
        lines.append(f"  <ItemGroup><ProjectReference Include=\"{ref}\" /></ItemGroup>")
    for package in packages or []:
        lines.append(f"  <ItemGroup><PackageReference Include=\"{package}\" Version=\"1.0.0\" /></ItemGroup>")
    lines.append("</Project>")
    write(root, rel, "\n".join(lines) + "\n")


def coverage(root: Path, rel: str, percent: int = 100) -> None:
    write(root, rel, json.dumps({"totals": {"lines": {"percent": percent},
                                            "branches": {"percent": percent}}}))


def service_manifest(name: str, root: str, *, workflow: bool = False,
                     vendor: bool = False) -> dict:
    layers = [
        {"name": "Api", "path": f"{root}/{name}.Api",
         "contracts": f"{root}/{name}.Api.Contracts"},
        {"name": "Application", "path": f"{root}/{name}.Application",
         "contracts": f"{root}/{name}.Application.Contracts"},
        {"name": "Domain", "path": f"{root}/{name}.Domain", "contracts": None},
        {"name": "Infrastructure", "path": f"{root}/{name}.Infrastructure"},
        {"name": "Host", "path": f"{root}/{name}.Host"},
    ]
    data = {
        "name": name,
        "path": root,
        "layers": layers,
        "domain": f"{root}/{name}.Domain",
        "domainTests": f"{root}/{name}.Domain.Tests",
        "coverage": {"line": 100, "branch": 100, "report": f"{root}/coverage.json"},
        "businessRules": [{"id": f"{name.upper()}-1", "test": f"{name}_rule_is_enforced"}],
    }
    if workflow:
        data["workflow"] = {
            "ui": f"{root}/{name}.Api/Workflow.cs",
            "api": f"{root}/{name}.Application/Workflow.cs",
            "states": ["Draft", "Submitted"],
            "transitions": [{"from": "Draft", "to": "Submitted", "event": "Submit"}],
            "errors": ["EmptyOrder"],
        }
    if vendor:
        data["vendors"] = [{"name": "Stripe", "adapter": f"{root}/{name}.Stripe",
                            "contracts": f"{root}/{name}.Stripe.Contracts",
                            "packages": ["Stripe.net"]}]
    return data


def build_good(root: Path) -> None:
    orders = "services/Orders"
    catalog = "services/Catalog"
    write(root, f"{orders}/README.md", "# Orders\n\n## Responsibility\n\nOwns the order lifecycle.\n")
    write(root, f"{catalog}/README.md", "# Catalog\n\n## Responsibility\n\nOwns the product catalog.\n")

    for service, name, workflow, vendor in ((orders, "Orders", True, True),
                                            (catalog, "Catalog", False, False)):
        for layer in service_manifest(name, service, workflow=workflow, vendor=vendor)["layers"]:
            csproj(root, f"{layer['path']}/{name}.{layer['name']}.csproj")
            if layer.get("contracts"):
                csproj(root, f"{layer['contracts']}/{name}.{layer['name']}.Contracts.csproj")
                write(root, f"{layer['contracts']}/{name}.{layer['name']}Contract.cs",
                      f"namespace {name}.{layer['name']}.Contracts;\n"
                      f"public sealed record {name}{layer['name']}Request(string Id);\n")
        csproj(root, f"{service}/{name}.Domain/{name}.Domain.csproj")
        csproj(root, f"{service}/{name}.Domain.Tests/{name}.Domain.Tests.csproj")
        write(root, f"{service}/{name}.Domain/Rule.cs",
              f"namespace {name}.Domain;\n// rule: {name.upper()}-1\npublic sealed class Rule {{ }}\n")
        write(root, f"{service}/{name}.Domain.Tests/RuleTests.cs",
              f"namespace {name}.Domain.Tests;\npublic sealed class RuleTests {{\n"
              f"  public void {name}_rule_is_enforced() {{ }}\n}}\n")
        coverage(root, f"{service}/coverage.json")

    write(root, f"{orders}/Orders.Api/Workflow.cs",
          "namespace Orders.Api;\n// workflow: Draft Submitted Submit EmptyOrder\n"
          "public sealed class Workflow { }\n")
    write(root, f"{orders}/Orders.Application/Workflow.cs",
          "namespace Orders.Application;\n// workflow: Draft Submitted Submit EmptyOrder\n"
          "public sealed class Workflow { }\n")
    write(root, f"{orders}/Orders.Api/PlaceOrderMapper.cs",
          "namespace Orders.Api;\npublic sealed class PlaceOrderMapper { }\n")
    write(root, f"{orders}/Orders.Application/PlaceOrderHandler.cs",
          "namespace Orders.Application;\npublic sealed class PlaceOrderHandler { }\n")

    csproj(root, f"{orders}/Orders.Stripe.Contracts/Orders.Stripe.Contracts.csproj")
    write(root, f"{orders}/Orders.Stripe.Contracts/IStripeGateway.cs",
          "namespace Orders.Stripe.Contracts;\npublic interface IStripeGateway { }\n")
    csproj(root, f"{orders}/Orders.Stripe/Orders.Stripe.csproj",
           refs=["../Orders.Stripe.Contracts/Orders.Stripe.Contracts.csproj"],
           packages=["Stripe.net"])
    write(root, f"{orders}/Orders.Stripe/StripeGateway.cs",
          "using Stripe.net;\nnamespace Orders.Stripe;\npublic sealed class StripeGateway { }\n")

    csproj(root, f"{orders}/Orders.Catalog/Orders.Catalog.csproj")
    write(root, f"{orders}/Orders.Catalog/CatalogRequest.cs",
          "namespace Orders.Catalog;\npublic sealed record CatalogRequest(string Id);\n")
    csproj(root, f"{orders}/Orders.Host/Orders.Host.csproj", packages=["Amazon.CDK"])
    write(root, f"{orders}/Orders.Host/Host.cs",
          "using Amazon.CDK;\nnamespace Orders.Host;\npublic sealed class Host { }\n")

    manifest = {
        "standard": "1.0.0",
        "profile": "service-topology",
        "services": [service_manifest("Orders", orders, workflow=True, vendor=True),
                     service_manifest("Catalog", catalog)],
        "interService": [{"name": "Orders.Catalog", "source": "Orders", "target": "Catalog",
                          "path": f"{orders}/Orders.Catalog"}],
        "boundaries": [
            {"caller": "Orders.Api", "callee": "Orders.Application",
             "callerContract": f"{orders}/Orders.Api.Contracts",
             "calleeContract": f"{orders}/Orders.Application.Contracts",
             "transform": f"{orders}/Orders.Api/PlaceOrderMapper.cs"},
            {"caller": "Orders.Application", "callee": "Orders.Domain",
             "callerContract": f"{orders}/Orders.Application.Contracts",
             "calleeContract": None,
             "transform": f"{orders}/Orders.Application/PlaceOrderHandler.cs"},
        ],
        "deploymentPackages": ["Amazon.CDK"],
    }
    write(root, "acima.topology.json", json.dumps(manifest, indent=2) + "\n")


def build_bad(root: Path) -> None:
    bad = "not-services/Bad"
    write(root, f"{bad}/README.md",
          "# Bad\n\n## Responsibility\n\nOwns the bad workflow. Also owns a second responsibility.\n")
    layers = [
        {"name": "Api", "path": f"{bad}/Bad.Wrong", "contracts": f"{bad}/Bad.Api.Contracts"},
        {"name": "Application", "path": f"{bad}/Bad.Application",
         "contracts": f"{bad}/Bad.Api.Contracts"},
        {"name": "Domain", "path": f"{bad}/Bad.Domain", "contracts": None},
        {"name": "Host", "path": f"{bad}/Bad.Host"},
    ]
    manifest = {
        "standard": "1.0.0",
        "profile": "service-topology",
        "services": [{
            "name": "Bad", "path": bad, "layers": layers,
            "domain": f"{bad}/Bad.Domain", "domainTests": f"{bad}/Bad.Domain.Tests",
            "coverage": {"line": 92, "branch": 92, "report": f"{bad}/coverage.json"},
            "businessRules": [{"id": "B-1", "test": "missing_test"}],
            "workflow": {
                "ui": f"{bad}/Bad.Wrong/Workflow.ts",
                "api": f"{bad}/Bad.Application/Workflow.ts",
                "states": ["Draft", "Submitted"],
                "transitions": [{"from": "Draft", "to": "Submitted", "event": "Submit"}],
                "errors": ["EmptyOrder"],
            },
            "vendors": [{"name": "Stripe", "adapter": f"{bad}/Bad.Stripe",
                         "contracts": f"{bad}/Bad.Stripe.Contracts",
                         "packages": ["Stripe.net"]}],
        }],
        "interService": [
            {"name": "Bad.Catalog", "source": "Bad", "target": "Catalog",
             "path": f"{bad}/Bad.Catalog"},
            {"name": "Bad.Catalog.Payments", "source": "Bad", "target": "Catalog",
             "path": f"{bad}/Bad.Catalog.Payments"},
        ],
        "boundaries": [{"caller": "Bad.Api", "callee": "Bad.Application",
                        "callerContract": f"{bad}/Bad.Api.Contracts",
                        "calleeContract": f"{bad}/Bad.Api.Contracts",
                        "transform": f"{bad}/missing.ts"}],
        "deploymentPackages": ["Amazon.CDK"],
    }
    write(root, "acima.topology.json", json.dumps(manifest, indent=2) + "\n")

    csproj(root, f"{bad}/Bad.Api.Contracts/Bad.Api.Contracts.csproj",
           refs=["../Bad.Domain/Bad.Domain.csproj"], packages=["Newtonsoft.Json"])
    write(root, f"{bad}/Bad.Api.Contracts/Contract.cs",
          "namespace Bad.Api.Contracts;\npublic sealed record BadRequest(string Id);\n")
    csproj(root, f"{bad}/Bad.Wrong/Bad.Wrong.csproj")
    write(root, f"{bad}/Bad.Wrong/Workflow.ts",
          "// workflow: Draft Submitted Submit\nexport interface Workflow { }\n")
    write(root, f"{bad}/Bad.Wrong/ReExport.ts",
          "export * from '../Bad.Application.Contracts/index.ts';\n")
    csproj(root, f"{bad}/Bad.Application/Bad.Application.csproj")
    write(root, f"{bad}/Bad.Application/Workflow.ts",
          "// workflow: Draft Submitted Submit EmptyOrder\nexport interface Workflow { }\n")
    csproj(root, f"{bad}/Bad.Domain/Bad.Domain.csproj")
    write(root, f"{bad}/Bad.Domain/Domain.cs",
          "using Microsoft.EntityFrameworkCore;\nusing Stripe.net;\nusing Amazon.CDK;\n"
          "namespace Bad.Domain;\npublic sealed class Domain { }\n")
    write(root, f"{bad}/Bad.Domain/deploy.tf", "resource \"x\" \"y\" {}\n")
    csproj(root, f"{bad}/Bad.Domain.Tests/Bad.Domain.Tests.csproj")
    write(root, f"{bad}/Bad.Domain.Tests/DomainTests.cs",
          "namespace Bad.Domain.Tests;\npublic sealed class DomainTests { }\n")
    coverage(root, f"{bad}/coverage.json", 92)
    csproj(root, f"{bad}/Bad.Host/Bad.Host.csproj", packages=["Amazon.CDK"])
    csproj(root, f"{bad}/Bad.Stripe.Contracts/Bad.Stripe.Contracts.csproj")
    write(root, f"{bad}/Bad.Stripe.Contracts/IStripeGateway.cs",
          "namespace Bad.Stripe.Contracts;\npublic interface IStripeGateway { }\n")
    csproj(root, f"{bad}/Bad.Stripe/Bad.Stripe.csproj",
           refs=["../Bad.Stripe.Contracts/Bad.Stripe.Contracts.csproj"],
           packages=["Stripe.net"])
    write(root, f"{bad}/Bad.Stripe/StripeGateway.cs",
          "using Stripe.net;\nnamespace Bad.Stripe;\npublic sealed class StripeGateway { }\n")
    csproj(root, f"{bad}/Bad.Catalog/Bad.Catalog.csproj")
    write(root, f"{bad}/Bad.Catalog/Contract.cs",
          "namespace Bad.Catalog;\npublic sealed record CatalogRequest(string Id);\n")
    csproj(root, f"{bad}/Bad.Catalog.Payments/Bad.Catalog.Payments.csproj")
    write(root, f"{bad}/Bad.Catalog.Payments/Contract.cs",
          "namespace Bad.Catalog.Payments;\npublic sealed record Payment(string Id);\n")
    write(root, "consumers/Third/Consumer.cs", "using Bad.Catalog;\npublic sealed class Consumer { }\n")


class TopologyTests(unittest.TestCase):
    def test_good_topology_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_good(root)
            findings = topology.Topology(root, "acima.topology.json").run()
            self.assertEqual([], [finding.as_dict() for finding in findings])

    def test_bad_topology_reports_every_st_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_bad(root)
            findings = topology.Topology(root, "acima.topology.json").run()
            rules = {finding.rule for finding in findings}
            expected = set(topology.ST_RULES.values())
            self.assertEqual(expected, rules)
            self.assertTrue(all(finding.severity == "error" for finding in findings))
            self.assertGreaterEqual(len(findings), 12)
            self.assertTrue(any(finding.rule == "ACIMA-S007"
                                and finding.path == "consumers/Third/Consumer.cs"
                                for finding in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
