// Candidate only: fingerprint executable AST, retaining full bodies/dependencies.
// This is a reviewed source boundary, not a heuristic JavaScript security proof.
const fs = require('node:fs');
const crypto = require('node:crypto');
const ts = require(process.argv[3]);
const source = ts.createSourceFile('LibraryIntelligence.tsx', fs.readFileSync(process.argv[2], 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const errors = source.parseDiagnostics.map(d => `PARSE_ERROR:${d.code}`);
if (source.pragmas.size) errors.push('UNREVIEWED_COMPILER_PRAGMA');
const passiveTags = new Set(['div','section','article','main','header','footer','aside','nav','p','span','h1','h2','h3','h4','h5','h6','dl','dt','dd','ul','ol','li','strong','em','small','br','hr']);
const interactionTags = new Set(['details','summary','label','progress','button']);
const presentationAttributes = new Set(['className','title','aria-label','aria-describedby','htmlFor','id']);
const jsxKind = n => ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n) || ts.isJsxFragment(n);
const digest = x => crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');

// Flatten only passive JSX wrappers/text. All JS expressions, component names,
// event handlers, spreads, props and conditional control remain in the digest.
function jsx(n) {
  if (ts.isJsxFragment(n)) return children(n.children);
  const opening = ts.isJsxElement(n) ? n.openingElement : n;
  const tag = opening.tagName.getText(source);
  const native = /^[a-z]/.test(tag);
  const passive = passiveTags.has(tag);
  if (native && !passive && !interactionTags.has(tag)) errors.push(`UNREVIEWED_HTML_CAPABILITY:${tag}`);
  const attrs = [];
  for (const a of opening.attributes.properties) {
    if (passive && ts.isJsxAttribute(a) && presentationAttributes.has(a.name.text) && a.initializer && ts.isStringLiteral(a.initializer)) continue;
    attrs.push(shape(a));
  }
  const child = ts.isJsxElement(n) ? children(n.children) : [];
  if (passive && attrs.length === 0) return child;
  return [['jsx', passive ? 'passive' : tag, attrs, child]];
}
function children(nodes) {
  const out = [];
  for (const n of nodes) {
    if (ts.isJsxText(n)) continue;
    if (jsxKind(n)) out.push(...jsx(n));
    else if (ts.isJsxExpression(n)) { if (n.expression) out.push(shape(n.expression)); }
    else out.push(shape(n));
  }
  return out;
}
function shape(n) {
  if (jsxKind(n)) return ['jsx-content', jsx(n)];
  if (ts.isJsxText(n)) return null;
  const value = ts.isIdentifier(n) || ts.isPrivateIdentifier(n) || ts.isLiteralExpression(n) || ts.isTemplateLiteralToken(n) ? n.text : null;
  const nested = [];
  ts.forEachChild(n, x => { nested.push(shape(x)); });
  return [n.kind, value, nested];
}
const sections = {};
source.statements.forEach((s, i) => { sections[`${i}:${ts.SyntaxKind[s.kind]}`] = digest(shape(s)); });
// Comments can carry compiler/bundler semantics (for example PURE annotations).
// The reviewed page has no comment markers. Pin the raw marker envelope rather
// than silently erasing directives as ordinary AST trivia. Layout/copy may evolve.
sections['source_comment_markers'] = digest(source.text.match(/\/\*|\/\//g) || []);
if (process.argv[4]) {
  const expected = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')).page_executable_sections;
  for (const key of new Set([...Object.keys(expected), ...Object.keys(sections)])) {
    if (sections[key] !== expected[key]) errors.push(`UNREVIEWED_EXECUTABLE_SECTION:${key}`);
  }
}
process.stdout.write(JSON.stringify({ok: errors.length === 0, errors: [...new Set(errors)], sections}));
