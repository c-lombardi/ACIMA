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
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, dirname, normalize, relative, resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';

const CATALOG = {
  'ACIMA-D001': ['error', 'L1'], 'ACIMA-D002': ['error', 'L1'], 'ACIMA-D003': ['error', 'L1'],
  'ACIMA-D004': ['error', 'L1'], 'ACIMA-D005': ['error', 'L1'], 'ACIMA-D006': ['error', 'L1'],
  'ACIMA-D007': ['error', 'L1'], 'ACIMA-D008': ['error', 'L1'], 'ACIMA-D009': ['error', 'L1'],
  'ACIMA-L001': ['error', 'L1'], 'ACIMA-L002': ['error', 'L1'], 'ACIMA-L003': ['error', 'L1'],
  'ACIMA-C001': ['error', 'L2'], 'ACIMA-C002': ['error', 'L2'], 'ACIMA-C004': ['error', 'L2'],
  'ACIMA-C005': ['error', 'L2'], 'ACIMA-C006': ['error', 'L2'],
  'ACIMA-A001': ['error', 'L3'], 'ACIMA-A003': ['error', 'L3'],
  'ACIMA-G001': ['error', 'L1'], 'ACIMA-G002': ['error', 'L1'],
  'ACIMA-G003': ['warning', 'L2'], 'ACIMA-G005': ['error', 'L1'],
};
const RANK = { L1: 1, L2: 2, L3: 3 };

const PERSISTENCE = ['@prisma/client', 'typeorm', 'sequelize', 'knex', 'pg', 'mysql2', 'mongodb', 'ioredis'];
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
const LEVEL = (arg('level', '') || 'L1').toUpperCase();

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
const level = arg('level', config.level || 'L1').toUpperCase();
const units = (config.units || []).map((u) => ({ ...u, paths: u.paths || [] }));
const excludes = config.exclude || ['node_modules', 'tests', 'violations'];
const moduleNames = new Set(units.filter((u) => u.module).map((u) => u.module));

const findings = [];
const files = new Map();      // rel -> source
const unitsOf = new Map();    // rel -> unit
const edges = [];             // { from, to, line, evidence }

const rel = (p) => relative(ROOT, p).split(sep).join('/');
const excluded = (r) => {
  const parts = r.split('/');
  return excludes.some((pattern) => {
    const clean = pattern.replace(/\*\*/g, '').replace(/\*/g, '');
    return r === pattern || parts.includes(clean) || parts.some((p) => p === clean);
  });
};

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stats = statSync(full);
    if (stats.isDirectory()) {
      if (!excluded(rel(full) + '/')) walk(full);
    } else if (entry.endsWith('.ts')) {
      const r = rel(full);
      if (!excluded(r)) files.set(r, readFileSync(full, 'utf8'));
    }
  }
}

function unitFor(r, source) {
  const head = source.split('\n').slice(0, 3).join('\n');
  const override = head.match(/acima-unit:\s*([\w.-]+)/);
  if (override) {
    const token = override[1];
    const exact = units.find((u) => u.id === token);
    if (exact) return exact;
    const impl = units.find((u) => u.module === token && u.role === 'implementation');
    if (impl) return impl;
    if (token.endsWith('.contracts')) {
      return units.find((u) => u.module === token.split('.')[0] && u.role === 'contracts');
    }
  }
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

function add(rule, message, path, line, evidence = '') {
  const [severity, required] = CATALOG[rule];
  if (RANK[required] > RANK[level]) return;
  findings.push({ rule, severity, message, path, line: Math.max(line, 1), evidence: evidence.slice(0, 200) });
}

function resolveSpecifier(spec, fromRel) {
  if (spec.startsWith('.')) {
    const target = normalize(join(dirname(join(ROOT, fromRel)), spec)).replace(/\.ts$/, '');
    for (const candidate of [`${target}.ts`, `${target}/index.ts`]) {
      const r = rel(candidate);
      if (files.has(r)) return r;
    }
    return null;
  }
  const alias = (config.aliases || {})[spec];
  if (alias) return alias.replace(/^\.\//, '');
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
    const unit = unitFor(r, source);
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
          add('ACIMA-D001',
            `Module ${from.module} imports the implementation unit ${to.id} (expected ${to.module}.contracts).`,
            r, line, evidence);
          const named = /\{([^}]*)\}/.exec(clause);
          if (named && named[1].split(',').some((n) => n.trim().replace(/^type\s+/, '').startsWith('_'))) {
            add('ACIMA-D009', `${from.module} imports a private type from module ${to.module}.`, r, line, evidence);
          }
          const types = publicTypes(target);
          if (types.size > 0) {
            add('ACIMA-L003',
              `implementation unit ${to.id} publishes the public type ${[...types].sort().join(', ')} outside the module`,
              target, 1);
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

    // C001 / C002 / C006: inspect each exported interface or class body
    const blockPattern = /export\s+(?:interface|class|type)\s+([A-Za-z0-9_]+)[^{=]*\{([\s\S]*?)\n\}/g;
    let block;
    while ((block = blockPattern.exec(source)) !== null) {
      const [, name, body] = block;
      const line = lineOf(source, block.index);
      let mutable = false;
      let offset = block.index;
      for (const raw of body.split('\n')) {
        const member = raw.trim();
        const memberIndex = body.indexOf(raw, offset - block.index);
        offset = block.index + memberIndex + raw.length;
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
      const before = source.slice(Math.max(0, block.index - 200), block.index);
      if (!/\*\/\s*$/.test(before)) {
        add('ACIMA-G003', `Contract type ${name} has no documentation.`, r, line);
      }
    }
  }
}

function lineOf(source, index) {
  return source.slice(0, index).split('\n').length;
}

function checkLayering() {
  for (const [r, source] of files) {
    const unit = unitsOf.get(r);
    if (unit.role !== 'implementation' || r.includes('/infrastructure/')) continue;
    for (const token of PERSISTENCE) {
      if (source.includes(`'${token}'`) || source.includes(`"${token}"`)) {
        add('ACIMA-L001', `${unit.id} references infrastructure (${token}) outside infrastructure/.`, r, lineOf(source, source.indexOf(token)), token);
      }
    }
  }
}

function checkSql() {
  for (const [r, source] of files) {
    const unit = unitsOf.get(r);
    const pattern = /(['"`])([^'"`]*?(?:from|into|update|join)\s+[a-z][a-z0-9_]*[^'"`]*?)\1/gi;
    let match;
    while ((match = pattern.exec(source)) !== null) {
      const inner = match[2];
      let sqlMatch;
      SQL.lastIndex = 0;
      while ((sqlMatch = SQL.exec(inner)) !== null) {
        const prefix = sqlMatch[1].split('_')[0];
        if (moduleNames.has(prefix) && prefix !== unit.module) {
          add('ACIMA-A001', `${unit.id} queries the ${prefix} schema (${sqlMatch[1]}); each module owns its own tables.`,
            r, lineOf(source, match.index), sqlMatch[1]);
        }
      }
    }
  }
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
    for (const { spec } of importsOf(source)) {
      const base = spec.split('/').pop()?.replace(/\.ts$/, '') || '';
      if (declarations.has(base)) {
        const decl = declarations.get(base);
        if (unitsOf.get(r)?.module !== decl.unit.module) {
          add('ACIMA-A003', `${unitsOf.get(r).id} imports and may mutate the static state ${base} owned by ${decl.unit.id}.`,
            decl.path, decl.line, base);
        }
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
    if (new Date(waiver.expires) < new Date()) {
      add('ACIMA-G002', `Waiver for ${waiver.rule} expired on ${waiver.expires} (owner: ${waiver.owner}).`, path, index + 1);
    } else {
      waivers.push(waiver);
    }
  });
  return waivers;
}

function applyWaivers(waivers) {
  const kept = findings.filter((finding) => {
    const unit = unitsOf.get(finding.path);
    return !waivers.some((w) => w.rule === finding.rule && unit && w.scope === `unit:${unit.id}`);
  });
  findings.length = 0;
  findings.push(...kept);
}

collect();
checkEdges();
checkContracts();
checkLayering();
checkSql();
checkStatics();
applyWaivers(checkWaivers());

const unique = new Map();
for (const finding of findings.sort((a, b) => (a.path + a.line + a.rule).localeCompare(b.path + b.line + b.rule))) {
  unique.set(`${finding.rule}|${finding.path}|${finding.line}`, finding);
}
const ordered = [...unique.values()].sort((a, b) => a.path.localeCompare(b.path) || a.line - b.line || a.rule.localeCompare(b.rule));
const errors = ordered.filter((f) => f.severity === 'error');

if (FORMAT === 'json') {
  console.log(JSON.stringify({ standard: config.standard || '1.0.0', level, findings: ordered }, null, 2));
} else {
  for (const f of ordered) {
    console.log(`${f.rule}  ${f.severity.padEnd(7)} ${f.message}\n  ${f.path}:${f.line}${f.evidence ? `\n  ${f.evidence}` : ''}`);
  }
  console.log(`\n${ordered.length} finding(s), ${errors.length} error(s) at level ${level}`);
}
process.exit(errors.length ? 1 : 0);
