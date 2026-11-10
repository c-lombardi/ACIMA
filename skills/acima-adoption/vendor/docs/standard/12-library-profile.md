# 12. Library and framework profile

ACIMA's base rules describe any software system: a module's implementation is private, and only its
contracts surface crosses the module boundary. A published library, framework, SDK or plugin system
has an additional, deliberate boundary — its **public package surface** — and, often, **adapters**
that exist precisely to depend on a driver, protocol or platform SDK. This profile does not define
what a module is, and a public package boundary is not automatically an ACIMA module boundary.

Applying the base rules to such a repository without a profile produces two opposite errors:

- a public type is reported as an implementation leak (`ACIMA-L003`), although publishing it is
  the product; and
- an intentional driver integration is reported as a layering violation (`ACIMA-L001`), although
  the integration is the reason the file exists.

The profile is the explicit, reviewable way to say which surfaces are intentional. It does **not**
turn findings off. It classifies a narrowly declared subset into a separate `classified` array in
the enforcer report, with the owner and reason attached, and leaves every other edge and every
other file subject to the unchanged rules.

> **Status.** Optional profile, version 1.0. The TypeScript and .NET reference enforcers implement
> it in this revision. A profile declaration is a local architecture decision, not a conformance
> claim, and it is not covered by `ACIMA-S001`–`S012`.

## 12.1 When the profile applies

Use it only when the repository **publishes** an artifact whose consumers are outside the owning
team's control. The evidence must come from the repository itself, not from its name:

| Language | Evidence required by the reference enforcer |
|---|---|
| TypeScript | `package.json` with a `name` and without `"private": true` |
| .NET | a project whose evaluated `IsPackable` is not `false` and whose evaluated `PackageId` is non-empty (declared, inherited, or SDK-defaulted), or an equivalent publish manifest |

A repository that contains both a software system and a library uses the profile for the library
units only; the non-library units keep the base interpretation. A monorepo MAY contain several
profile declarations, one per published package, but each is reviewed separately. The profile is
available to published packages, public API surfaces, frameworks, SDKs and reusable libraries; it is
not required merely because a package is distributed.

If the evidence is ambiguous — a private package consumed only by sibling workspaces, an
unpublished "library" directory, an internal SDK — the classification requires a named human
confirmation before the profile is committed. The enforcer's own manifest check is a floor, not a
substitute for review.

## 12.2 Declaration

```json
{
  "packages": {
    "acme-widgets": { "path": "src" }
  },
  "profile": {
    "kind": "library",
    "owner": "platform-team",
    "justification": "Published package: adapter packages consume the root package as their public surface.",
    "publicApi": [
      { "unit": "core", "paths": ["src/index.ts"] }
    ],
    "intentionalAdapters": [
      {
        "from": "adapters",
        "to": "core",
        "paths": ["adapters/driver/**"],
        "owner": "platform-team",
        "reason": "Driver packages consume the published root package."
      },
      {
        "from": "adapters",
        "specifiers": ["mysql2"],
        "paths": ["adapters/driver/**"],
        "owner": "platform-team",
        "reason": "The MySQL driver is the integration itself."
      }
    ]
  }
}
```

`packages` is not part of the profile: it tells the resolver that a bare import such as
`acme-widgets` is this repository's own package, so the edge is analysed instead of being treated
as external. That is what turns a probable false negative into a real, reviewable dependency.

## 12.3 Semantics

1. **`publicApi` is path-scoped.** Each entry names one unit and the files that constitute its
   published surface. A bare unit id is rejected (`ACIMA-G001`): the whole unit would become
   exempt, including its internal files.
2. **`intentionalAdapters` are path- and specifier-scoped.** An entry applies only to findings
   whose file matches `paths`. A finding outside those paths is still reported, even if the same
   adapter package produced it. This is what stops a profile from hiding a newly introduced leak.
3. **Classification is reported, not deleted.** Every classified finding appears in the report's
   `classified` array with `rule`, `path`, `classification` (`intentional-adapter` or
   `declared-public-api`), `owner`, `reason`, and the declaration it matched. The `findings` array
   and the exit code contain only unclassified findings.
4. **Only three rules can be classified.** `ACIMA-D001` and `ACIMA-D009` for a declared
   adapter-to-target edge, `ACIMA-L001` for a declared specifier on a declared path, and
   `ACIMA-L003` for a file listed in `publicApi`. Every other rule — cycles (`D005`), transitive
   exposure (`D008`), kernel and contracts rules, contract design (`C`), persistence ownership
   (`A001`, `A003`), waivers (`G001`, `G002`) — is unaffected.
5. **Invalid declarations are findings.** A missing owner, reason or justification; an unknown
   unit; an adapter with no `paths`; a `publicApi` entry with no `paths`; an unsupported `kind`;
   or a library claim without publishable evidence produces `ACIMA-G001` and the run fails.
6. **The profile does not waive.** A waiver still needs its own owner, reason, fingerprint and
   expiry. A classified finding needs a declaration that is visible in review; neither mechanism
   replaces the other.

## 12.4 What must be verified

For every profile adoption:

- the declared `publicApi` files are the ones the package actually publishes (`exports`, `files`,
  `PackageId`, or an equivalent manifest);
- each declared adapter is a real integration point, not a wrapper introduced to silence a
  finding;
- removing the profile would produce the findings the declaration claims to explain — record that
  before/after pair in the adoption evidence;
- a new, undeclared edge in the same package still fails the gate. Add a fixture for it, as
  `conformance/test_library_profile.py` does.

## 12.5 Limitations

- Classification is declarative. It records a reviewed decision; it does not prove the decision is
  architecturally sound.
- Path globs are matched against repository-relative POSIX paths by the enforcer, not by the build
  system. Files outside the declared paths keep the base interpretation. The .NET enforcer treats
  `**/` as zero or more directories; glob semantics are not yet uniform across all reference
  enforcers, so a portable profile should use explicit paths or verify the pattern in the target
  enforcer.
- The profile is implemented by the TypeScript and .NET reference enforcers in this revision.
  Python and Go have no profile support; using one there is a no-op, and a repository MUST NOT
  assume its declaration is enforced.
- A public surface is not automatically a contracts unit. The profile records that publishing is
  intended; it does not claim the published types satisfy chapter 5.
