// The architecture gate: the good tree must be clean, and the gallery must match the
// documented findings exactly. If either drifts, the build fails.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const run = (args) => spawnSync(process.execPath, ['tools/acima-arch.mjs', ...args], { cwd: root, encoding: 'utf8' });

test('production code has no findings', () => {
  const result = run(['--root', '.', '--format', 'json']);
  const payload = JSON.parse(result.stdout);
  assert.deepEqual(payload.findings, [], 'the reference implementation must be clean');
  assert.equal(result.status, 0);
});

test('gallery matches the documented findings', () => {
  const result = run(['--root', '.', '--config', 'acima.gallery.config.json', '--format', 'json']);
  const payload = JSON.parse(result.stdout);
  const actual = {};
  for (const finding of payload.findings) (actual[finding.rule] ??= new Set()).add(finding.path);
  const expected = JSON.parse(readFileSync(join(root, 'violations/expected.json'), 'utf8'));
  assert.deepEqual(
    Object.fromEntries(Object.entries(actual).map(([k, v]) => [k, [...v].sort()])),
    Object.fromEntries(Object.entries(expected).map(([k, v]) => [k, [...v].sort()])),
  );
});

test('every finding carries the required fields', () => {
  const result = run(['--root', '.', '--config', 'acima.gallery.config.json', '--format', 'json']);
  const { findings } = JSON.parse(result.stdout);
  assert.ok(findings.length > 0, 'a suite that finds nothing proves nothing');
  for (const finding of findings) {
    for (const key of ['rule', 'severity', 'message', 'path', 'line']) assert.ok(key in finding, key);
    assert.match(finding.rule, /^ACIMA-[A-Z]\d{3}$/);
    assert.ok(['error', 'warning', 'info'].includes(finding.severity));
  }
});

test('tool failure is not reported as architecture debt', () => {
  const result = run(['--root', '.', '--config', 'nope.json', '--format', 'json']);
  assert.equal(result.status, 2);
  assert.match(result.stderr, /cannot read config/);
});
