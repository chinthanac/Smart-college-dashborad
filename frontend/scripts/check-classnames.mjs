#!/usr/bin/env node
/**
 * Cross-checks every className used in JSX against every class selector the
 * stylesheets define, and fails if a class is used with no rule behind it.
 *
 * This exists because that exact drift shipped twice and nobody noticed:
 *
 *   - the dashboard's Quick Actions markup was renamed .action-* to .quick-*
 *     and the stylesheet was not, so the admin landing page rendered a stack
 *     of bare buttons against dead CSS;
 *   - the assessments, marks and results screens were written with eleven
 *     class names that were never styled, so those panels inherited whatever
 *     .panel happened to give them.
 *
 * Neither is a crash, and neither shows up in a build. They only show up if
 * somebody happens to look at the right screen at the right width — which is
 * precisely the kind of thing a machine should be checking instead.
 *
 * Deliberately dependency-free: it is a hundred lines of string handling, and
 * the project does not add packages it can write.
 *
 * Usage:  node scripts/check-classnames.mjs [--list-unused]
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

// fileURLToPath, not URL.pathname: this project's checkout has a space in its
// path ("College Management"), which pathname would hand back percent-encoded.
const ROOT = fileURLToPath(new URL('..', import.meta.url));
const SRC = join(ROOT, 'src');

/**
 * Classes that are intentionally referenced without a rule of their own.
 * Keep this short and justify every entry — it is an escape hatch, not a
 * dumping ground.
 */
const ALLOWED_WITHOUT_RULE = new Set([
  // Applied by AdminSidebar and only ever read by its own :not()/combinator
  // rules, never styled directly.
]);

const walk = (dir, out = []) => {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
};

const files = walk(SRC);
const jsxFiles = files.filter((f) => f.endsWith('.jsx'));
const cssFiles = files.filter((f) => f.endsWith('.css'));

if (!jsxFiles.length || !cssFiles.length) {
  console.error('check-classnames: found no .jsx or no .css files under src/');
  process.exit(2);
}

// --------------------------------------------------------------------------
// what the stylesheets define
// --------------------------------------------------------------------------

const defined = new Set();

for (const file of cssFiles) {
  const css = readFileSync(file, 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    // Drop at-rule preludes *with* their opening brace, so a rule nested in a
    // @media block is read as an ordinary rule. Without this the first
    // selector inside every media query is swallowed — which is how
    // `.tt-day-full`, defined only at the 900px breakpoint, was reported
    // missing when it was not.
    .replace(/@[\w-]+[^{;]*\{/gi, '');

  // Everything before a `{` is a selector list. Splitting on `}` first keeps
  // declaration bodies (where `0.82rem` lives) out of the selector text.
  for (const block of css.split('}')) {
    const selectorText = block.slice(0, block.indexOf('{'));
    if (!selectorText || selectorText.trimStart().startsWith('@')) continue;
    for (const match of selectorText.matchAll(/\.(-?[A-Za-z_][\w-]*)/g)) {
      defined.add(match[1]);
    }
  }
}

// --------------------------------------------------------------------------
// what the JSX uses
// --------------------------------------------------------------------------

// Stands in for a ${...} interpolation so a fragment glued to one is dropped
// rather than reported as a missing class (`color-${n}` must not become
// `color-`).
const HOLE = '\u0000';

const used = new Map(); // class -> Set of "path:line"

const recordUse = (name, file, line) => {
  if (!name || name.includes(HOLE)) return;
  if (!/^-?[A-Za-z_][\w-]*$/.test(name)) return;
  const where = `${relative(ROOT, file)}:${line}`;
  if (!used.has(name)) used.set(name, new Set());
  used.get(name).add(where);
};

/**
 * A string literal in a braced className is usually a class — but not when it
 * is the right-hand side of a comparison or the argument to a string
 * predicate. `className={`btn ${tab === 'sessions' ? 'is-selected' : ''}`}`
 * uses 'is-selected' as a class and 'sessions' as data, and reporting the
 * latter as a missing rule would train people to ignore this script.
 */
const OPERAND_BEFORE = /(?:===|!==|==|!=|\b(?:includes|startsWith|endsWith|indexOf|match)\s*\()\s*$/;
const OPERAND_AFTER = /^\s*(?:===|!==|==|!=)/;

/** Reads a brace-balanced `{...}` expression starting at the opening brace. */
const readBraced = (source, start) => {
  let depth = 0;
  for (let i = start; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === '{') depth += 1;
    else if (ch === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(start + 1, i);
    }
  }
  return null;
};

const harvest = (expr, file, line) => {
  // Template literals first: the static text between interpolations is class
  // names. The interpolated code is kept so the quoted-literal pass below can
  // still see any classes inside it.
  const rest = expr.replace(/`([^`]*)`/g, (_, body) => {
    for (const name of body.replace(/\$\{[^}]*\}/g, HOLE).split(/\s+/)) {
      recordUse(name, file, line);
    }
    return (body.match(/\$\{[^}]*\}/g) ?? []).join(' ');
  });

  for (const lit of rest.matchAll(/'([^']*)'|"([^"]*)"/g)) {
    const before = rest.slice(0, lit.index);
    const after = rest.slice(lit.index + lit[0].length);
    if (OPERAND_BEFORE.test(before) || OPERAND_AFTER.test(after)) continue;
    for (const name of (lit[1] ?? lit[2] ?? '').split(/\s+/)) {
      recordUse(name, file, line);
    }
  }
};

for (const file of jsxFiles) {
  const source = readFileSync(file, 'utf8');
  const lineOf = (index) => source.slice(0, index).split('\n').length;

  for (const match of source.matchAll(/className=/g)) {
    const at = match.index + match[0].length;
    const line = lineOf(match.index);

    if (source[at] === '"' || source[at] === "'") {
      const quote = source[at];
      const end = source.indexOf(quote, at + 1);
      if (end === -1) continue;
      for (const name of source.slice(at + 1, end).split(/\s+/)) {
        recordUse(name, file, line);
      }
    } else if (source[at] === '{') {
      const expr = readBraced(source, at);
      if (expr !== null) harvest(expr, file, line);
    }
  }
}

// --------------------------------------------------------------------------
// report
// --------------------------------------------------------------------------

const missing = [...used.keys()]
  .filter((name) => !defined.has(name) && !ALLOWED_WITHOUT_RULE.has(name))
  .sort();

if (process.argv.includes('--list-unused')) {
  const unused = [...defined].filter((name) => !used.has(name)).sort();
  console.log(`\nDefined in CSS but used by no JSX (${unused.length}):`);
  for (const name of unused) console.log(`  .${name}`);
}

console.log(
  `\nchecked ${jsxFiles.length} jsx files against ${cssFiles.length} stylesheet(s): ` +
    `${used.size} classes used, ${defined.size} defined`,
);

if (!missing.length) {
  console.log('✓ every class used in JSX has a rule behind it\n');
  process.exit(0);
}

console.error(`\n✗ ${missing.length} class(es) used in JSX with no CSS rule:\n`);
for (const name of missing) {
  console.error(`  .${name}`);
  for (const where of [...used.get(name)].sort()) console.error(`      ${where}`);
}
console.error(
  '\nEither add the rule, or add the class to ALLOWED_WITHOUT_RULE in this ' +
    'script with a reason.\n',
);
process.exit(1);
