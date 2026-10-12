// Read-only TypeScript inventory. The compiler supplies nested route ancestry.
const fs = require('fs'), path = require('path')
const root = path.resolve(__dirname, '..'), ts = require(path.join(root, 'frontend/node_modules/typescript'))
const files = [], routes = [], modules = []
function scan(dir) { for (const e of fs.readdirSync(dir, {withFileTypes:true})) { const p=path.join(dir,e.name); if(e.isDirectory())scan(p);else if(/\.(tsx?|css)(\.backup)?$/.test(p))files.push(p) } }
scan(path.join(root,'frontend/src'))
function attrs(node) { const opening=ts.isJsxElement(node)?node.openingElement:node; const out={}; for(const a of opening.attributes.properties){ if(ts.isJsxAttribute(a))out[a.name.getText()]=a.initializer?ts.isStringLiteral(a.initializer)?a.initializer.text:a.initializer.getText():true } return out }
function name(node) { return (ts.isJsxElement(node)?node.openingElement:node).tagName.getText() }
for(const file of files.filter(p=>!/\.css$/.test(p))) {
  const source=fs.readFileSync(file,'utf8'), sf=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
  const entry={file:path.relative(root,file).replaceAll('\\','/'),lines:source.split('\n').length,imports:[],exports:[],functions:[],jsx:[],hooks:[],api_calls:[]}
  function walk(n) {
    if(ts.isImportDeclaration(n))entry.imports.push(n.moduleSpecifier.text)
    if(ts.isFunctionDeclaration(n)&&n.name){entry.functions.push(n.name.text); if(n.modifiers?.some(m=>m.kind===ts.SyntaxKind.ExportKeyword))entry.exports.push(n.name.text)}
    if(ts.isVariableStatement(n)&&n.modifiers?.some(m=>m.kind===ts.SyntaxKind.ExportKeyword))for(const d of n.declarationList.declarations)entry.exports.push(d.name.getText())
    if(ts.isCallExpression(n)) {const callee=n.expression.getText();if(/^use[A-Z]/.test(callee))entry.hooks.push(callee);if(/request|Api|getBooks|getBook|searchBooks|ReadingList|lendingCommand/.test(callee))entry.api_calls.push(n.getText().slice(0,220))}
    if(ts.isJsxElement(n)||ts.isJsxSelfClosingElement(n)) {
      const tag=name(n); entry.jsx.push(tag)
      if(tag==='Route') {const a=attrs(n), segments=[a.path||''];let p=n.parent;while(p){if(ts.isJsxElement(p)&&name(p)==='Route'){const b=attrs(p);segments.unshift(b.path||'')}p=p.parent}const route=segments.join('/').replace(/\/+ /g,'/').replace(/\/{2,}/g,'/'); routes.push({route:route||'/',index:!!a.index,element:a.element||'',file:entry.file,line:sf.getLineAndCharacterOfPosition(n.getStart()).line+1})}
    }
    ts.forEachChild(n,walk)
  }
  walk(sf);for(const k of ['functions','exports','jsx','hooks'])entry[k]=[...new Set(entry[k])];modules.push(entry)
}
fs.writeFileSync(path.join(root,'reports/full_product_frontend_discovery.json'),JSON.stringify({routes,modules},null,2))
console.log(`Discovered ${routes.length} route declarations, ${modules.length} TypeScript modules.`)
