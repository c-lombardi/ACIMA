#!/usr/bin/env node
/**
 * ACIMA reference enforcer for TypeScript.
 *
 * Implements the portable rule set against the units declared in acima.config.json.
 * Reads source text; never imports or executes the product code.
 *
 *   node tools/acima-arch.mjs --root . --config acima.config.json --format json
 *
 * Exit codes: 0 clean, 1 unwaived errors, 2 tool failure.
 */
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, dirname, normalize, relative, resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';

const CATALOG = {
  'ACIMA-D001': ['error', 'L1'], 'ACIMA-D002': ['error', 'L1'], 'ACIMA-D003': ['error', 'L1'],
  'ACIMA-D004': ['error', 'L1'], 'ACIMA-D005': ['error', 'L1'], 'ACIMA-D006': ['error', 'L1'],
  'ACIMA-D007': ['error', 'L1'], 'ACIMA-D008': ['error', 'L1'], 'ACIMA-D009': ['error', 'L1'],
  'ACIMA-L001': ['error', 'L1'], 'ACIMA-L002': ['error', 'L1'], 'ACIMA-L003': ['error', 'L1'],
  'ACIMA-L004': ['warning', 'L1'],
  'ACIMA-D010': ['error', 'L1'],
  'ACIMA-L005': ['warning', 'L1'], 'ACIMA-L006': ['error', 'L1'], 'ACIMA-L007': ['warning', 'L1'],
  'ACIMA-C001': ['error', 'L2'], 'ACIMA-C002': ['error', 'L2'], 'ACIMA-C003': ['error', 'L2'],
  'ACIMA-C004': ['error', 'L2'], 'ACIMA-C005': ['error', 'L2'], 'ACIMA-C006': ['error', 'L2'],
  'ACIMA-C007': ['warning', 'L2'],
  'ACIMA-A001': ['error', 'L3'], 'ACIMA-A002': ['warning', 'L3'],
  'ACIMA-A003': ['error', 'L3'], 'ACIMA-A004': ['warning', 'L3'],
  'ACIMA-G001': ['error', 'L1'], 'ACIMA-G002': ['error', 'L1'],
  'ACIMA-G003': ['warning', 'L2'], 'ACIMA-G004': ['error', 'L2'],
  'ACIMA-G005': ['error', 'L1'], 'ACIMA-G006': ['warning', 'L1'],
};
const NOT_EXECUTED = {
  'ACIMA-C003': 'behaviour versus validation is a semantic judgement',
  'ACIMA-C007': 'constructor completeness needs symbol and API analysis',
  'ACIMA-L004': 'service-locator APIs are framework-specific',
  'ACIMA-A002': 'configuration APIs differ per ecosystem',
  'ACIMA-A004': 'version-lock coupling is visible only across published packages',
  'ACIMA-G004': 'an API baseline needs a per-language surface format',
};
const RANK = { L1: 1, L2: 2, L3: 3 };
// Third-party governance: the tier rules only execute when externals is declared.
const TIER_RULES = ['ACIMA-L005', 'ACIMA-L006', 'ACIMA-L007', 'ACIMA-D010', 'ACIMA-G006'];
const TIERS = ['platform', 'integration', 'utility'];
const ENTRY_FIELDS = ['tier', 'owner', 'reason', 'reviewedOn', 'expires'];

const PERSISTENCE = ['@prisma/client', 'typeorm', 'sequelize', 'knex', 'pg', 'mysql2', 'mongodb', 'ioredis', 'DbContext', 'PrismaClient', 'EntityManager', 'IQueryable', 'MongoClient'];
const FRAMEWORK = ['express', 'fastify', 'koa', '@nestjs/core', 'hono', 'next', 'react', 'node:http'];
const AMBIENT = [/new Date\(/, /Date\.now\(/, /crypto\.randomUUID\(/, /Math\.random\(/, /performance\.now\(/];
const SQL = /\b(?:from|into|update|join)\s+([a-z][a-z0-9_]*)/gi;
const UNTYPED = /:\s*(any|unknown|object)\b|Record<string,\s*(any|unknown|object)>/;

const args = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const ROOT = resolve(process.cwd(), arg('root', '.'));
const CONFIG = arg('config', 'acima.config.json');
const FORMAT = arg('format', 'text');

function fail(message) {
  console.error(`acima: ${message}`);
  process.exit(2);
}

let config;
try {
  config = JSON.parse(readFileSync(join(ROOT, CONFIG), 'utf8'));
} catch (error) {
  fail(`cannot read config ${CONFIG}: ${error.message}`);
}
const level = String(arg('level', '') || config.level || 'L1').toUpperCase();
if (!RANK[level]) fail(`unknown level ${level}; expected L1, L2 or L3`);
const units = (config.units || []).map((u) => ({ ...u, paths: u.paths || [] }));
const excludes = config.exclude || ['node_modules', 'tests', 'violations'];
const moduleNames = new Set(units.filter((u) => u.module).map((u) => u.module));

// Optional, explicit architecture profile. A library's published surface and its
// intentional adapters are classified, never silently suppressed: every classified
// finding still appears in the JSON report with its owner and reason.
const profile = config.profile && typeof config.profile === 'object' ? config.profile : null;
const profileKind = profile ? String(profile.kind || '') : '';
const profilePublicApi = Array.isArray(profile?.publicApi) ? profile.publicApi : [];
const profileAdapters = Array.isArray(profile?.intentionalAdapters) ? profile.intentionalAdapters : [];
const workspacePackages = config.packages && typeof config.packages === 'object' ? config.packages : {};
const externals = config.externals && typeof config.externals === 'object' && !Array.isArray(config.externals)
  ? config.externals
  : null;
const manifests = Array.isArray(config.manifests) ? config.manifests.map(String) : [];
let configText = '';
try { configText = readFileSync(join(ROOT, CONFIG), 'utf8'); } catch { configText = ''; }
const classified = [];

const findings = [];
const files = new Map();      // rel -> source
const unitsOf = new Map();    // rel -> unit
const edges = [];             // { from, to, line, evidence }

const rel = (p) => relative(ROOT, p).split(sep).join('/');
const excluded = (r) => {
  const value = r.replace(/\/$/, '');
  const parts = value.split('/');
  return excludes.some((raw) => {
    let pattern = String(raw).trim().replace(/\\/g, '/');
    if (pattern.startsWith('./')) pattern = pattern.slice(2);
    pattern = pattern.replace(/\/+$/, '');
    if (!pattern) return false;
    // Glob patterns such as **/*.test.ts must be matched as globs, not as
    // literal fragments. Literal paths match a file or a directory subtree;
    // a bare segment keeps the legacy "any directory named tests" behaviour.
    if (pattern.includes('*')) return globMatch(value, pattern);
    return value === pattern || value.startsWith(pattern + '/') || parts.includes(pattern);
  });
};

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stats = statSync(full);
    if (stats.isDirectory()) {
      if (!excluded(rel(full) + '/')) walk(full);
    } else if (/\.(?:ts|tsx|js|mjs|cjs)$/.test(entry)) {
      const r = rel(full);
      if (!excluded(r)) files.set(r, readFileSync(full, 'utf8'));
    }
  }
}

function unitByPath(r) {
  let best = null;
  for (const unit of units) {
    for (const path of unit.paths) {
      if ((r === path || r.startsWith(path.replace(/\/$/, '') + '/')) &&
          (!best || path.length > best.path.length)) {
        best = { unit, path };
      }
    }
  }
  return best ? best.unit : null;
}

function overrideUnit(source) {
  const head = source.split('\n').slice(0, 3).join('\n');
  const override = head.match(/acima-unit:\s*([\w.-]+)/);
  if (!override) return null;
  const token = override[1];
  const exact = units.find((u) => u.id === token);
  if (exact) return exact;
  const impl = units.find((u) => u.module === token && u.role === 'implementation');
  if (impl) return impl;
  if (token.endsWith('.contracts')) {
    return units.find((u) => u.module === token.split('.')[0] && u.role === 'contracts');
  }
  return null;
}

function unitFor(r, source) {
  return overrideUnit(source) || unitByPath(r);
}

function findingFingerprint(rule, path, evidence) {
  return 'sha256:' + createHash('sha256')
    .update(`${rule}\0${path}\0${evidence}`)
    .digest('hex').slice(0, 16);
}

function add(rule, message, path, line, evidence = '') {
  if (!CATALOG[rule]) return;
  const [severity, required] = CATALOG[rule];
  if (RANK[required] > RANK[level]) return;
  const trimmed = evidence.slice(0, 200);
  findings.push({ rule, severity, message, path, line: Math.max(line, 1),
    evidence: trimmed, fingerprint: findingFingerprint(rule, path, trimmed) });
}

function pathDeclared(adapter, path) {
  const patterns = Array.isArray(adapter.paths) ? adapter.paths : [];
  return patterns.some((pattern) => {
    const literal = String(pattern).replace(/\*+$/, '');
    return globMatch(path, String(pattern)) || (literal && path.startsWith(literal));
  });
}

function adapterFor(fromUnit, toUnit, specifier, path) {
  return profileAdapters.find((adapter) => {
    if (!adapter || adapter.from !== fromUnit?.id) return false;
    if (!pathDeclared(adapter, path)) return false;
    if (toUnit) {
      if (!adapter.to || adapter.to !== toUnit.id) return false;
    }
    if (specifier) {
      const specs = Array.isArray(adapter.specifiers) ? adapter.specifiers : [];
      if (!specs.some((candidate) => specifier === candidate || specifier.startsWith(`${candidate}/`))) return false;
    }
    return Boolean(adapter.to || (adapter.specifiers || []).length);
  });
}

function classifyAdapter(rule, path, line, evidence, fromUnit, toUnit, specifier) {
  const adapter = adapterFor(fromUnit, toUnit, specifier, path);
  if (!adapter) return false;
  classified.push({
    rule, path, line: Math.max(line, 1), evidence: evidence.slice(0, 200),
    classification: 'intentional-adapter', declaredBy: adapter.from,
    target: adapter.to || null, owner: adapter.owner, reason: adapter.reason,
  });
  return true;
}

function classifyPublicApi(rule, path, line, evidence, unit) {
  const entry = profilePublicApi.find((candidate) => {
    if (!candidate || candidate.unit !== unit?.id) return false;
    return (Array.isArray(candidate.paths) ? candidate.paths : []).some((pattern) => {
      const literal = String(pattern).replace(/\*+$/, '');
      return globMatch(path, String(pattern)) || (literal && path.startsWith(literal));
    });
  });
  if (!entry) return false;
  classified.push({
    rule, path, line: Math.max(line, 1), evidence: evidence.slice(0, 200),
    classification: 'declared-public-api', declaredBy: entry.unit,
    owner: profile.owner || '', reason: profile.justification || '',
  });
  return true;
}

function validateProfile() {
  if (!profile) return;
  if (profileKind !== 'application' && profileKind !== 'library') {
    add('ACIMA-G001', `profile.kind is ${JSON.stringify(profile.kind)}; expected "application" or "library".`,
      CONFIG, 1, 'profile.kind');
    return;
  }
  if (!String(profile.justification || '').trim()) {
    add('ACIMA-G001', 'profile has no justification; it would be an undocumented exemption.',
      CONFIG, 1, 'profile.justification');
  }
  if (!String(profile.owner || '').trim()) {
    add('ACIMA-G001', 'profile has no owner; an exception without an owner is not reviewable.',
      CONFIG, 1, 'profile.owner');
  }
  if (profileKind === 'library') {
    // A monorepo root is usually private; the evidence is whichever declared
    // workspace package is actually published.
    const candidates = [join(ROOT, 'package.json')];
    for (const value of Object.values(workspacePackages)) {
      const base = typeof value === 'string' ? value : value && value.path;
      if (!base) continue;
      if (value && value.manifest) candidates.push(join(ROOT, value.manifest));
      candidates.push(join(ROOT, base, 'package.json'));
      candidates.push(join(ROOT, base, '..', 'package.json'));
    }
    // A monorepo root is often private while its sibling packages are published.
    try {
      for (const entry of readdirSync(ROOT)) candidates.push(join(ROOT, entry, 'package.json'));
    } catch (error) {
      // best effort: the root manifest remains the evidence
    }
    const publishable = candidates.some((candidate) => {
      try {
        const manifest = JSON.parse(readFileSync(candidate, 'utf8'));
        return Boolean(String(manifest.name || '').trim()) && manifest.private !== true;
      } catch (error) {
        return false;
      }
    });
    if (!publishable) {
      add('ACIMA-G001', 'library profile is not supported by the repository manifests: no root or declared workspace package is named and publishable.',
        CONFIG, 1, 'profile.kind');
    }
  }
  for (const entry of profilePublicApi) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
      add('ACIMA-G001', 'profile.publicApi entries must be objects with unit and paths; a bare unit is a blanket exemption.',
        CONFIG, 1, 'profile.publicApi');
      continue;
    }
    if (!units.some((unit) => unit.id === entry.unit)) {
      add('ACIMA-G001', `profile.publicApi names the unknown unit ${entry.unit}.`, CONFIG, 1, 'profile.publicApi');
    }
    if (!Array.isArray(entry.paths) || entry.paths.length === 0) {
      add('ACIMA-G001', `profile.publicApi for ${entry.unit} declares no paths; the whole unit would become public.`,
        CONFIG, 1, 'profile.publicApi');
    }
  }
  for (const adapter of profileAdapters) {
    const missing = ['from', 'owner', 'reason'].filter((key) => !String(adapter?.[key] || '').trim());
    if (missing.length > 0) {
      add('ACIMA-G001', `intentional adapter is missing: ${missing.join(', ')}.`,
        CONFIG, 1, 'profile.intentionalAdapters');
      continue;
    }
    if (!units.some((unit) => unit.id === adapter.from)) {
      add('ACIMA-G001', `intentional adapter names the unknown unit ${adapter.from}.`,
        CONFIG, 1, 'profile.intentionalAdapters');
    }
    if (adapter.to && !units.some((unit) => unit.id === adapter.to)) {
      add('ACIMA-G001', `intentional adapter names the unknown target ${adapter.to}.`,
        CONFIG, 1, 'profile.intentionalAdapters');
    }
    if (!Array.isArray(adapter.paths) || adapter.paths.length === 0) {
      add('ACIMA-G001', `intentional adapter ${adapter.from} declares no paths; a whole-unit exemption can hide new edges.`,
        CONFIG, 1, 'profile.intentionalAdapters');
    }
    if (!adapter.to && (!Array.isArray(adapter.specifiers) || adapter.specifiers.length === 0)) {
      add('ACIMA-G001', `intentional adapter ${adapter.from} declares neither a target unit nor specifiers.`,
        CONFIG, 1, 'profile.intentionalAdapters');
    }
  }
}

function resolveSpecifier(spec, fromRel) {
  if (spec.startsWith('.')) {
    const target = normalize(join(dirname(join(ROOT, fromRel)), spec)).replace(/\.(?:ts|tsx|js|mjs|cjs)$/, '');
    for (const extension of ['.ts', '.tsx', '.js', '.mjs', '.cjs']) {
      const candidate = rel(`${target}${extension}`);
      if (files.has(candidate)) return candidate;
    }
    for (const extension of ['.ts', '.tsx', '.js', '.mjs', '.cjs']) {
      const candidate = rel(`${target}/index${extension}`);
      if (files.has(candidate)) return candidate;
    }
    return null;
  }
  const alias = (config.aliases || {})[spec];
  if (alias) return alias.replace(/^\.\//, '');
  // Workspace packages declared in the config resolve to their source, so an
  // adapter that imports the published package name is a real internal edge
  // rather than an external dependency. Undeclared packages stay external.
  for (const [name, value] of Object.entries(workspacePackages)) {
    if (spec !== name && !spec.startsWith(`${name}/`)) continue;
    const base = typeof value === 'string' ? value : value && value.path;
    if (!base) continue;
    const sub = spec === name ? '' : spec.slice(name.length + 1);
    const stem = rel(resolve(ROOT, base, sub));
    for (const extension of ['.ts', '.tsx', '.js', '.mjs', '.cjs']) {
      if (stem && files.has(`${stem}${extension}`)) return `${stem}${extension}`;
    }
    for (const extension of ['.ts', '.tsx', '.js', '.mjs', '.cjs']) {
      const candidate = rel(resolve(ROOT, base, sub, `index${extension}`));
      if (files.has(candidate)) return candidate;
    }
    return undefined;
  }
  return undefined; // external
}

function importsOf(source) {
  const out = [];
  const pattern = /((?:import|export)[\s\S]*?from\s+)['"]([^'"]+)['"]|(import\s*\(\s*)['"]([^'"]+)['"]/g;
  let match;
  while ((match = pattern.exec(source)) !== null) {
    const spec = match[2] || match[4];
    const clause = match[1] || match[3] || '';
    const line = source.slice(0, match.index).split('\n').length;
    out.push({ spec, clause, line, evidence: match[0].replace(/\s+/g, ' ').trim() });
  }
  const requirePattern = /require\s*\(\s*['"]([^'"]+)['"]\s*\)/g;
  while ((match = requirePattern.exec(source)) !== null) {
    out.push({
      spec: match[1], clause: 'require', line: source.slice(0, match.index).split('\n').length,
      evidence: match[0].replace(/\s+/g, ' ').trim(),
    });
  }
  return out;
}

function publicTypes(r) {
  const source = files.get(r) || '';
  const names = new Set();
  const pattern = /export\s+(?:abstract\s+)?(?:class|interface|type|enum|function)\s+([A-Za-z0-9_]+)/g;
  let match;
  while ((match = pattern.exec(source)) !== null) names.add(match[1]);
  return names;
}

function collect() {
  walk(ROOT);
  for (const [r, source] of [...files.entries()]) {
    const declared = unitByPath(r);
    const unit = unitFor(r, source);
    if (declared && unit && declared.id !== unit.id) {
      add('ACIMA-G005', `Role override changes ${r} from ${declared.id} to ${unit.id}.`, r, 1, 'acima-unit override');
    }
    if (!unit) {
      add('ACIMA-G005', `Source file is not part of any declared unit: ${r}`, r, 1);
      files.delete(r);
      continue;
    }
    unitsOf.set(r, unit);
  }
}

function moduleEdges() {
  const graph = new Map([...moduleNames].map((m) => [m, new Set()]));
  for (const { from, to } of edges) {
    const a = unitsOf.get(from);
    const b = unitsOf.get(to);
    if (a?.module && b?.module && a.module !== b.module) graph.get(a.module).add(b.module);
  }
  return graph;
}

function checkEdges() {
  for (const [r, source] of files) {
    const from = unitsOf.get(r);
    for (const { spec, clause, line, evidence } of importsOf(source)) {
      const target = resolveSpecifier(spec, r);
      if (target === undefined) {
        const top = spec.split('/')[0];
        if (from.role === 'contracts') {
          add('ACIMA-D004', `contracts unit ${from.id} depends on third-party package: ${spec}`, r, line, evidence);
        } else if (from.role === 'shared-kernel') {
          add('ACIMA-D007', `shared kernel depends on a third-party package: ${spec}`, r, line, evidence);
        }
        continue;
      }
      if (target === null || !unitsOf.has(target)) continue;
      const to = unitsOf.get(target);
      edges.push({ from: r, to: target, line, evidence });
      if (['host', 'tooling', 'test'].includes(from.role)) continue;

      if (from.role === 'shared-kernel') {
        if (to.role !== 'shared-kernel') {
          add('ACIMA-D007', `shared kernel references ${to.id}; the kernel must be a leaf.`, r, line, evidence);
        }
        continue;
      }
      if (from.role === 'contracts') {
        if (to.role === 'implementation') {
          add('ACIMA-D002', `${from.id} references the implementation unit ${to.id}.`, r, line, evidence);
        } else if (to.role === 'contracts' && to.module !== from.module) {
          add('ACIMA-D003', `${from.id} references ${to.id}; contracts must be independent.`, r, line, evidence);
        } else if (to.role === 'host') {
          add('ACIMA-D006', `${from.id} references the host unit; contracts must not know how they are hosted.`, r, line, evidence);
        }
        continue;
      }
      if (from.role === 'implementation') {
        if (to.role === 'host') {
          add('ACIMA-D006', `${from.id} references the host unit.`, r, line, evidence);
        } else if (to.role === 'implementation' && to.module !== from.module) {
          if (!classifyAdapter('ACIMA-D001', r, line, evidence, from, to)) {
            add('ACIMA-D001',
              `Module ${from.module} imports the implementation unit ${to.id} (expected ${to.module}.contracts).`,
              r, line, evidence);
          }
          const named = /\{([^}]*)\}/.exec(clause);
          if (named && named[1].split(',').some((n) => n.trim().replace(/^type\s+/, '').startsWith('_'))) {
            if (!classifyAdapter('ACIMA-D009', r, line, evidence, from, to)) {
              add('ACIMA-D009', `${from.module} imports a private type from module ${to.module}.`, r, line, evidence);
            }
          }
          const types = publicTypes(target);
          if (types.size > 0) {
            const message = `implementation unit ${to.id} publishes the public type ${[...types].sort().join(', ')} outside the module`;
            if (!classifyPublicApi('ACIMA-L003', target, 1, message, to)) {
              add('ACIMA-L003', message, target, 1);
            }
          }
        }
      }
    }
  }
  checkCycles();
  checkTransitive();
}

function checkCycles() {
  const graph = moduleEdges();
  const state = new Map();
  const stack = [];
  const reported = new Set();
  const visit = (node) => {
    state.set(node, 1);
    stack.push(node);
    for (const next of [...graph.get(node)].sort()) {
      if (!state.get(next)) visit(next);
      else if (state.get(next) === 1) {
        const cycle = [...stack.slice(stack.indexOf(next)), next];
        const key = cycle.join('>');
        if (!reported.has(key)) {
          reported.add(key);
          const edge = edges.find((e) => unitsOf.get(e.from)?.module === node && unitsOf.get(e.to)?.module === next);
          add('ACIMA-D005', `Circular module dependency: ${cycle.join(' -> ')}`, edge ? edge.from : [...files.keys()][0], 1);
        }
      }
    }
    stack.pop();
    state.set(node, 2);
  };
  for (const node of [...graph.keys()].sort()) if (!state.get(node)) visit(node);
}

function checkTransitive() {
  const graph = new Map();
  for (const { from, to } of edges) {
    const a = unitsOf.get(from);
    const b = unitsOf.get(to);
    if (!a || !b) continue;
    if (!graph.has(a.id)) graph.set(a.id, new Set());
    graph.get(a.id).add(b.id);
  }
  const byId = new Map(units.map((u) => [u.id, u]));
  const seen = new Set();
  for (const edge of edges) {
    const a = unitsOf.get(edge.from);
    const b = unitsOf.get(edge.to);
    if (!a || !b || a.module === b.module) continue;
    if (!['contracts', 'implementation'].includes(a.role)) continue;
    const reachable = new Set([b.id]);
    const queue = [b.id];
    while (queue.length > 0) {
      const node = queue.shift();
      for (const next of graph.get(node) || []) {
        if (!reachable.has(next)) { reachable.add(next); queue.push(next); }
      }
    }
    for (const id of [...reachable].sort()) {
      const target = byId.get(id);
      if (!target || target.module === a.module || target.role !== 'implementation') continue;
      // D008 is transitive exposure. Repeating the direct edge that D001 already
      // reports is duplicate output, not additional coverage.
      if (id === b.id) continue;
      const key = `${a.id}>${target.id}`;
      if (seen.has(key)) continue;
      seen.add(key);
      add('ACIMA-D008',
        `${a.id} reaches the implementation unit ${target.id} transitively through ${b.id}.`,
        edge.from, edge.line, edge.evidence);
    }
  }
}

function checkContracts() {
  for (const [r, source] of files) {
    const unit = unitsOf.get(r);
    if (unit.role !== 'contracts') continue;

    for (const pattern of AMBIENT) {
      const match = pattern.exec(source);
      if (match) add('ACIMA-C004', `contracts unit ${unit.id} reads ambient state (${match[0]}).`, r, lineOf(source, match.index), match[0]);
    }
    for (const token of PERSISTENCE) {
      if (source.includes(token)) add('ACIMA-C005', `contracts unit ${unit.id} exposes a persistence concern (${token}).`, r, lineOf(source, source.indexOf(token)), token);
    }
    for (const token of FRAMEWORK) {
      if (new RegExp(`from\\s+['"]${token.replace(/[/.]/g, '\\$&')}`).test(source)) {
        add('ACIMA-L002', `contracts unit ${unit.id} exposes a framework type (${token}).`, r, lineOf(source, source.indexOf(token)), token);
      }
    }

    // C001 / C002 / C006: inspect every exported interface, class or object type.
    for (const block of contractBlocks(source)) {
      const { name, body, bodyStart, line } = block;
      let mutable = false;
      let cursor = 0;
      for (const raw of body.split(/[\n;]+/)) {
        const member = raw.trim();
        const local = body.indexOf(raw, cursor);
        if (local < 0) continue;
        cursor = local + raw.length;
        const memberIndex = bodyStart + local;
        if (!member || member.startsWith('*') || member.startsWith('/') || member.startsWith('//')) continue;
        const isProperty = /^(?:(?:public|private|protected|static|readonly|declare)\s+)*[A-Za-z_]\w*\??\s*:/.test(member);
        if (!isProperty) continue;
        if (!/\breadonly\b/.test(member)) mutable = true;
        const declared = member.split(':').slice(1).join(':').replace(/;$/, '').trim();
        const mutableArray = (/\[\]$/.test(declared) && !/^readonly\s/.test(declared)) || /^Array</.test(declared);
        if (mutableArray) {
          add('ACIMA-C002', `Contract type ${name} exposes a mutable collection (${member}).`, r, lineOf(source, memberIndex), member);
        }
        if (UNTYPED.test(member)) {
          add('ACIMA-C006', `Contract type ${name} has an untyped member (${member.split(':').slice(1).join(':').trim()}).`, r, lineOf(source, memberIndex), member);
        }
      }
      if (mutable) {
        add('ACIMA-C001', `Contract type ${name} exposes mutable state (missing readonly).`, r, line);
      }
      const before = source.slice(Math.max(0, block.start - 200), block.start);
      if (!/\*\/\s*$/.test(before)) {
        add('ACIMA-G003', `Contract type ${name} has no documentation.`, r, line);
      }
    }
  }
}

function contractBlocks(source) {
  const blocks = [];
  const pattern = /export\s+(?:interface|class|type)\s+([A-Za-z0-9_]+)/g;
  let match;
  while ((match = pattern.exec(source)) !== null) {
    const rest = source.slice(match.index);
    const brace = rest.indexOf('{');
    if (brace < 0) continue;
    const equals = rest.indexOf('=');
    if (match[0].startsWith('export type') && (equals < 0 || equals > brace)) continue;
    let depth = 0;
    let end = -1;
    for (let i = brace; i < rest.length; i++) {
      if (rest[i] === '{') depth++;
      else if (rest[i] === '}') {
        depth--;
        if (depth === 0) { end = i; break; }
      }
    }
    if (end < 0) continue;
    blocks.push({
      name: match[1], start: match.index, bodyStart: match.index + brace + 1,
      body: rest.slice(brace + 1, end), line: lineOf(source, match.index),
    });
    pattern.lastIndex = match.index + end + 1;
  }
  return blocks;
}

function lineOf(source, index) {
  return source.slice(0, index).split('\n').length;
}

function checkLayering() {
  for (const [r, source] of files) {
    const unit = unitsOf.get(r);
    if (unit.role !== 'implementation' || r.includes('/infrastructure/')) continue;
    if (r.includes('/tests/') || /\.(?:test|spec)\.[cm]?[jt]sx?$/.test(r)) continue;
    for (const imported of importsOf(source)) {
      // A declared integration library is governed by L005/L007, not the L001 token list.
      if (tierOf(imported.spec) === 'integration') continue;
      const token = PERSISTENCE.find((candidate) =>
        imported.spec === candidate || imported.spec.startsWith(`${candidate}/`));
      if (!token) continue;
      if (!classifyAdapter('ACIMA-L001', r, imported.line, imported.evidence, unit, null, imported.spec)) {
        add('ACIMA-L001',
          `${unit.id} imports infrastructure (${imported.spec}) outside infrastructure/.`,
          r, imported.line, imported.evidence);
      }
    }
  }
}

function externalEntry(spec) {
  if (!externals || !spec) return null;
  const candidates = [spec, spec.split('/')[0], spec.split('.')[0]]
    .filter(Boolean).map((value) => value.replace(/-/g, '_'));
  let best = null;
  for (const [name, raw] of Object.entries(externals)) {
    const entry = raw && typeof raw === 'object' ? raw : {};
    const extra = Array.isArray(entry.specifiers) ? entry.specifiers.map(String) : [];
    const known = [name, ...extra].map((value) => String(value).replace(/-/g, '_'));
    if (!candidates.some((value) => known.includes(value))) continue;
    if (!best || name.length > best.name.length) best = { name, entry };
  }
  return best;
}

function tierOf(spec) {
  const found = externalEntry(spec);
  return found ? String(found.entry.tier || '').trim() : null;
}

function vendorTokens(name, entry) {
  // A declared list is authoritative. Deriving from the package name is a fallback, and it is
  // deliberately not combined with the declaration: `monaco-editor` yields `MonacoEditor`, which
  // is the adapter's own class name far more often than a vendor type.
  const declared = (Array.isArray(entry.types) ? entry.types : [])
    .map(String).filter((token) => token.trim());
  if (declared.length > 0) return declared.filter((token) => token.length >= 3);
  const leaf = name.split('/').pop().split('.').pop();
  const tokens = new Set([name, leaf,
    leaf.split(/[^A-Za-z0-9]+/).filter(Boolean)
      .map((part) => part[0].toUpperCase() + part.slice(1)).join('')]);
  return [...tokens].filter((token) => token.length >= 3);
}

function manifestDependencies() {
  const out = [];
  const candidates = manifests.length > 0 ? manifests
    : ['package.json', 'pyproject.toml', 'requirements.txt']
      .filter((name) => existsSync(join(ROOT, name)));
  for (const relative of candidates) {
    const full = join(ROOT, relative);
    if (!existsSync(full)) continue;
    const text = readFileSync(full, 'utf8');
    if (relative.endsWith('.json')) {
      let data;
      try { data = JSON.parse(text); } catch { continue; }
      for (const name of Object.keys(data.dependencies || {})) {
        out.push({ path: relative, line: lineOf(text, text.indexOf(`"${name}"`)), package: name });
      }
    } else if (relative.endsWith('.txt')) {
      text.split(/\r?\n/).forEach((line, index) => {
        const value = line.trim();
        if (!value || value.startsWith('#') || value.startsWith('-')) return;
        const name = value.split(/[<>=!~\[\]; ]/)[0];
        if (name) out.push({ path: relative, line: index + 1, package: name });
      });
    }
  }
  return out;
}

function checkExternals() {
  if (!externals) return;
  const configRel = CONFIG;
  const entryLine = (name) => {
    const index = configText.indexOf(`"${name}"`);
    return index < 0 ? 1 : lineOf(configText, index);
  };
  const adapterUnits = new Map(units.filter((unit) => unit.role === 'adapter').map((unit) => [unit.id, unit]));
  const portUnits = new Map(units.filter((unit) => unit.role === 'port').map((unit) => [unit.id, unit]));
  const declaredAdapters = new Set();

  for (const [name, raw] of Object.entries(externals)) {
    const entry = raw && typeof raw === 'object' ? raw : {};
    const missing = ENTRY_FIELDS.filter((field) => !String(entry[field] || '').trim());
    if (missing.length > 0) {
      add('ACIMA-G001', `externals entry ${name} is missing: ${missing.join(', ')}.`, configRel, entryLine(name), name);
      continue;
    }
    const tier = String(entry.tier || '').trim();
    if (!TIERS.includes(tier)) {
      add('ACIMA-G001', `externals entry ${name} has unknown tier ${tier || '(empty)'}; expected ${TIERS.join(', ')}.`, configRel, entryLine(name), name);
      continue;
    }
    if (tier !== 'integration') continue;
    const adapter = String(entry.adapter || '').trim();
    const port = String(entry.port || '').trim();
    if (!adapter || !port) {
      add('ACIMA-L006', `integration entry ${name} declares no ${adapter ? 'port' : 'adapter'}; an adapter without a port is an unguarded vendor import.`, configRel, entryLine(name), name);
      continue;
    }
    if (!adapterUnits.has(adapter)) {
      add('ACIMA-G001', `externals entry ${name} names adapter ${adapter}, which is not a declared adapter unit.`, configRel, entryLine(name), name);
      continue;
    }
    if (!portUnits.has(port)) {
      add('ACIMA-G001', `externals entry ${name} names port ${port}, which is not a declared port unit.`, configRel, entryLine(name), name);
      continue;
    }
    declaredAdapters.add(adapter);
  }

  for (const unitId of [...adapterUnits.keys()].sort()) {
    if (declaredAdapters.has(unitId)) continue;
    const first = [...unitsOf.entries()].filter(([, unit]) => unit.id === unitId).map(([path]) => path).sort()[0];
    add('ACIMA-L006', `adapter unit ${unitId} is declared in no externals entry; it has no port and no reviewed vendor.`, first || configRel, 1, unitId);
  }

  for (const [r, source] of files) {
    const unit = unitsOf.get(r);
    for (const imported of importsOf(source)) {
      const found = externalEntry(imported.spec);
      if (!found) continue;
      const { name, entry } = found;
      if (unit.role === 'port') {
        add('ACIMA-D010', `port unit ${unit.id} imports the third-party package ${imported.spec}; a port declares the capability, never the vendor.`, r, imported.line, imported.evidence);
        continue;
      }
      if (String(entry.tier || '').trim() !== 'integration' || unit.role === 'adapter') continue;
      const declared = String(entry.adapter || '').trim();
      add('ACIMA-L005', `${unit.id} imports the integration library ${name}; only its adapter (${declared || 'undeclared'}) may import it, everyone else takes the port.`, r, imported.line, imported.evidence);
    }
  }

  // One adapter may cover a vendor and its wrapper (`monaco-editor` and `@monaco-editor/react`),
  // and both can declare the same worker type. Report one finding per line, named after the
  // shortest declaring package — the underlying vendor rather than the wrapper around it.
  const claimed = new Set();
  const entries = Object.entries(externals)
    .sort((a, b) => a[0].length - b[0].length || a[0].localeCompare(b[0]));
  for (const [name, raw] of entries) {
    const entry = raw && typeof raw === 'object' ? raw : {};
    const tier = String(entry.tier || '').trim();
    if (tier !== 'integration' && tier !== 'utility') continue;
    const tokens = vendorTokens(name, entry);
    for (const [r, source] of files) {
      const unit = unitsOf.get(r);
      if (unit.role === 'adapter') continue;
      source.split(/\r?\n/).forEach((text, index) => {
        const key = `${r}:${index + 1}`;
        if (claimed.has(key)) return;
        const stripped = text.trim();
        if (!stripped || stripped.startsWith('//') || stripped.startsWith('*')) return;
        if (stripped.startsWith('import ') || stripped.startsWith('from ')) return;
        // A vendor type is usually qualified (`monaco.editor.IStandaloneCodeEditor`), so only a
        // word character excludes a match; a dot must not.
        const hit = tokens.find((token) => new RegExp(`(?<![\\w])${token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![\\w])`).test(text));
        if (!hit) return;
        claimed.add(key);
        if (unit.role === 'port') {
          add('ACIMA-D010', `port unit ${unit.id} names the vendor type ${hit} from ${name}.`, r, index + 1, hit);
        } else if (tier === 'utility' && unit.role !== 'contracts') {
          return;
        } else {
          add('ACIMA-L007', `${unit.id} names the vendor type ${hit} from ${name} outside its adapter.`, r, index + 1, hit);
        }
      });
    }
  }

  const declared = new Set(Object.keys(externals).map((name) => name.replace(/-/g, '_').toLowerCase()));
  for (const dependency of manifestDependencies()) {
    if (declared.has(dependency.package.replace(/-/g, '_').toLowerCase())) continue;
    add('ACIMA-G006', `manifest dependency ${dependency.package} has no externals entry: declare its tier, owner and review date.`, dependency.path, dependency.line, dependency.package);
  }
  for (const [name, raw] of Object.entries(externals)) {
    const entry = raw && typeof raw === 'object' ? raw : {};
    const expires = String(entry.expires || '').trim();
    if (!expires) continue;
    const parsed = new Date(expires);
    if (Number.isNaN(parsed.getTime())) {
      add('ACIMA-G001', `externals entry ${name} has a non-ISO expiry: ${expires}.`, configRel, entryLine(name), name);
    } else if (parsed < new Date()) {
      add('ACIMA-G006', `externals entry ${name} passed its review date on ${expires}; renew or remove the dependency.`, configRel, entryLine(name), name);
    }
  }
}

function stringLiterals(source) {
  const out = [];
  let quote = null;
  let start = -1;
  for (let i = 0; i < source.length; i++) {
    const char = source[i];
    if (quote) {
      if (char === '\\') { i++; continue; }
      if (char === quote) {
        out.push({ text: source.slice(start + 1, i), index: start });
        quote = null;
      }
    } else if (char === "'" || char === '"' || char === '`') {
      quote = char;
      start = i;
    }
  }
  return out;
}

function checkSql() {
  for (const [r, source] of files) {
    const unit = unitsOf.get(r);
    for (const literal of stringLiterals(source)) {
      SQL.lastIndex = 0;
      let sqlMatch;
      while ((sqlMatch = SQL.exec(literal.text)) !== null) {
        const prefix = sqlMatch[1].split('_')[0];
        if (moduleNames.has(prefix) && prefix !== unit.module) {
          add('ACIMA-A001', `${unit.id} queries the ${prefix} schema (${sqlMatch[1]}); each module owns its own tables.`,
            r, lineOf(source, literal.index), sqlMatch[1]);
        }
      }
    }
  }
}

function importedNames(clause) {
  const names = [];
  const braces = /\{([^}]*)\}/.exec(clause);
  if (braces) {
    for (const raw of braces[1].split(',')) {
      const name = raw.trim().replace(/^type\s+/, '').split(/\s+as\s+/)[0].trim();
      if (name) names.push(name);
    }
  }
  const defaultImport = /^import\s+(?:type\s+)?([A-Za-z_$][\w$]*)\s*(?:,|from)/.exec(clause);
  if (defaultImport) names.push(defaultImport[1]);
  return names;
}

function checkStatics() {
  const declarations = new Map();
  for (const [r, source] of files) {
    const unit = unitsOf.get(r);
    if (!['implementation', 'shared-kernel'].includes(unit.role)) continue;
    const pattern = /^export\s+(?:const|let|var)\s+([A-Za-z0-9_]+)\s*(?::[^=]+)?=\s*([{[])/gm;
    let match;
    while ((match = pattern.exec(source)) !== null) {
      declarations.set(match[1], { path: r, line: lineOf(source, match.index), unit });
    }
  }
  for (const [r, source] of files) {
    for (const { clause } of importsOf(source)) {
      for (const name of importedNames(clause)) {
        if (!declarations.has(name)) continue;
        const decl = declarations.get(name);
        if (unitsOf.get(r)?.module === decl.unit.module) continue;
        add('ACIMA-A003', `${unitsOf.get(r).id} imports and may mutate the static state ${name} owned by ${decl.unit.id}.`,
          decl.path, decl.line, name);
      }
    }
  }
}

function checkWaivers() {
  const waivers = [];
  const path = config.waivers;
  if (!path) return waivers;
  let data;
  try {
    data = JSON.parse(readFileSync(join(ROOT, path), 'utf8'));
  } catch (error) {
    add('ACIMA-G001', `waivers file is missing or invalid: ${path}`, path, 1);
    return waivers;
  }
  const required = ['rule', 'scope', 'owner', 'reason', 'expires', 'reviewedOn'];
  (data.waivers || []).forEach((waiver, index) => {
    const missing = required.filter((key) => !String(waiver[key] || '').trim());
    if (missing.length) {
      add('ACIMA-G001', `Waiver for ${waiver.rule || '?'} is missing: ${missing.join(', ')}.`, path, index + 1);
      return;
    }
    if (!CATALOG[waiver.rule]) {
      add('ACIMA-G001', `Waiver names an unknown rule: ${waiver.rule}.`, path, index + 1);
      return;
    }
    const expiry = new Date(waiver.expires);
    if (Number.isNaN(expiry.getTime())) {
      add('ACIMA-G001', `Waiver expiry is not an ISO date: ${waiver.expires}.`, path, index + 1);
    } else if (expiry < new Date()) {
      add('ACIMA-G002', `Waiver for ${waiver.rule} expired on ${waiver.expires} (owner: ${waiver.owner}).`, path, index + 1);
    } else if (!String(waiver.fingerprint || '').trim()) {
      add('ACIMA-G001', `Waiver for ${waiver.rule} has no finding fingerprint; a broad waiver can hide future findings.`, path, index + 1);
    } else {
      waivers.push(waiver);
    }
  });
  return waivers;
}

function globMatch(value, pattern) {
  const escaped = pattern
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*\*/g, '\u0000')
    .replace(/\*/g, '[^/]*')
    .replace(/\u0000/g, '.*');
  return new RegExp(`^${escaped}$`).test(value);
}

function applyWaivers(waivers) {
  const kept = findings.filter((finding) => {
    const unit = unitsOf.get(finding.path);
    return !waivers.some((waiver) => {
      if (waiver.rule !== finding.rule) return false;
      if (!waiver.fingerprint || waiver.fingerprint !== finding.fingerprint) return false;
      if (waiver.scope === `unit:${unit?.id}`) return true;
      if (waiver.scope === `module:${unit?.module}`) return true;
      return waiver.scope.startsWith('path:') && globMatch(finding.path, waiver.scope.slice(5));
    });
  });
  findings.length = 0;
  findings.push(...kept);
}

collect();
validateProfile();
checkEdges();
checkContracts();
checkLayering();
checkSql();
checkStatics();
checkExternals();
applyWaivers(checkWaivers());

const unique = new Map();
for (const finding of findings.sort((a, b) => (a.path + a.line + a.rule).localeCompare(b.path + b.line + b.rule))) {
  unique.set(`${finding.rule}|${finding.path}|${finding.line}`, finding);
}
const ordered = [...unique.values()].sort((a, b) => a.path.localeCompare(b.path) || a.line - b.line || a.rule.localeCompare(b.rule));
const errors = ordered.filter((f) => f.severity === 'error');

const disabled = externals ? null : 'externals map not declared in acima.config.json';
const execution = Object.fromEntries(Object.keys(CATALOG).sort().map((rule) => [
  rule,
  NOT_EXECUTED[rule]
    ? { executed: false, reason: NOT_EXECUTED[rule] }
    : TIER_RULES.includes(rule) && disabled
      ? { executed: false, reason: disabled }
      : { executed: true },
]));

const profileSummary = profile
  ? { kind: profileKind, owner: profile.owner || null, justification: profile.justification || '',      publicApi: profilePublicApi.map((entry) => ({ unit: entry?.unit, paths: [...(entry?.paths || [])].sort() })),
      intentionalAdapters: profileAdapters.length
  }
  : null;

if (FORMAT === 'json') {
  console.log(JSON.stringify({ standard: config.standard || '1.0.0', level, sourceFiles: files.size,
    profile: profileSummary, execution, classified, findings: ordered }, null, 2));
} else {
  for (const f of ordered) {
    console.log(`${f.rule}  ${f.severity.padEnd(7)} ${f.message}\n  ${f.path}:${f.line}${f.evidence ? `\n  ${f.evidence}` : ''}`);
  }
  if (classified.length > 0) {
    console.log(`\n${classified.length} classified finding(s) (declared public API or intentional adapters)`);
  }
  console.log(`\n${ordered.length} finding(s), ${errors.length} error(s) at level ${level}`);
}
// Set the exit code instead of calling process.exit(): a large JSON report written
// to a pipe must be allowed to drain. process.exit() truncates at the pipe buffer
// (65536 bytes on Linux), which turns a complete assessment into invalid JSON.
process.exitCode = errors.length ? 1 : 0;
