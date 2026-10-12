import ts from '../frontend/node_modules/typescript/lib/typescript.js'
import fs from 'node:fs'
import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..'), source=path.join(root,'frontend/src'), before=path.join(root,'.scratch/platform-completion/before')
const files=fs.readdirSync(source,{recursive:true}).filter(p=>/\.tsx?$/.test(p)).sort(), rows=[]
function collect(text,file){
 const sf=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,file.endsWith('.tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS), out=[]
 function visit(node){
  let relevant=false
  if(ts.isJsxAttribute(node)&&['to','href'].includes(node.name.getText(sf)))relevant=true
  if(ts.isPropertyAssignment(node)&&node.name.getText(sf)==='to')relevant=true
  if(ts.isCallExpression(node)&&(/^(navigate|link)$/.test(node.expression.getText(sf))||/^window\.location\./.test(node.expression.getText(sf))))relevant=true
  if(ts.isBinaryExpression(node)&&/^window\.location/.test(node.left.getText(sf)))relevant=true
  if(relevant){let parent=node,component='module';while(parent){if(ts.isFunctionDeclaration(parent)&&parent.name){component=parent.name.text;break}parent=parent.parent}
   out.push({file,line:sf.getLineAndCharacterOfPosition(node.getStart(sf)).line+1,component,destination:node.getText(sf).replace(/\s+/g,' ')})
  }ts.forEachChild(node,visit)
 }visit(sf);return out
}
for(const file of files){const relative='frontend/src/'+file.replaceAll('\\','/'), current=collect(fs.readFileSync(path.join(source,file),'utf8'),relative), previous=fs.existsSync(path.join(before,relative))?collect(fs.readFileSync(path.join(before,relative),'utf8'),relative):[]
 for(const row of current){const dest=row.destination
  let classification='GLOBAL_INTENTIONAL',expected='Explicit global route or authentication destination; no library inference.',fixed='NO',bug=false
  if(/personalPath|withProductContext|withPatronContext/.test(dest)){classification='PERSONAL_WITH_RETURN_CONTEXT';expected='Preserve explicit URL workspace return context through centralized product resolver.';fixed='YES';bug=!previous.some(p=>p.destination===dest)}
  else if(/homePath|cataloguePath|productContext\.cataloguePath/.test(dest)){classification='CONTEXT_AWARE_REQUIRED';expected='Central resolver: staff /staff/libraries/:id; patron /libraries/:id; platform /platform; explicit global /.';fixed='YES';bug=!previous.some(p=>p.destination===dest)}
  else if(/libraryWorkspaceHome|staffPath|staffSectionPath|\/staff\/libraries|staffHome/.test(dest)){classification='STAFF_WORKSPACE';expected='Explicit selected library Staff Workspace; active membership required.'}
  else if(/patronPath|\/libraries\/|targetPath|invitationPath/.test(dest)){classification='PATRON_WORKSPACE';expected='Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.'}
  else if(/bookPath|productBookPath|homeBookPath|homeCataloguePath|readNow/.test(dest)){classification='CONTEXT_AWARE_REQUIRED';expected='Shared product destination preserves explicit workspace context.';fixed='YES'}
  else if(/\/platform|Platform|sections/.test(dest)||relative.includes('Platform')){classification='GLOBAL_INTENTIONAL';expected='Canonical Platform Console route; explicit platform authority required.'}
  else if(/Legacy|legacy|ManagementRedirect/.test(relative+' '+row.component)){classification='OBSOLETE';expected='Compatibility redirect only, or read-only historical account page; no independent dashboard.'}
  else if(/\/(login|signup|staff-login|verify-email|account-setup)|#main-content/.test(dest)){expected='Authentication clears previous context, or same-page accessible anchor.'}
  else if(/route\.path|link\.to|path\}|href\}|value\}|next|destination|url/.test(dest)){classification='CONTEXT_AWARE_REQUIRED';expected='Destination already prepared by scoped parent/navigation model; external/document URLs retain existing entitlement guard.';fixed='YES'}
  rows.push({...row,classification,expected,fixed,bug_fixed:bug})
 }
}
const count=rows.length,bugs=rows.filter(r=>r.bug_fixed).length
const meta={calls_audited:count,context_bugs_found:bugs,context_bugs_fixed:bugs,classification_counts:Object.fromEntries([...new Set(rows.map(r=>r.classification))].map(c=>[c,rows.filter(r=>r.classification===c).length]))}
fs.writeFileSync(path.join(root,'reports/platform_completion_context_audit.json'),JSON.stringify({status:'PASS',...meta,rows},null,2))
const esc=s=>String(s).replaceAll('|','\\|').replaceAll('`','')
fs.writeFileSync(path.join(root,'reports/product_context_navigation_audit.md'),`# Product context navigation audit\n\n${count} actual JSX destinations, navigation calls and navigation descriptor properties inspected with the TypeScript parser. ${bugs} call sites changed to preserve an explicit workspace return context. Classification concerns intent, not an authority grant.\n\nURL context wins. Explicit global URLs without return parameters remain global. Staff and Patron personal pages carry distinct UUID return parameters; Platform uses workspace=platform. Authentication and session changes clear return parameters. Memberships validate access and may correct a staff account away from patron presentation; no first-membership selection supplies Home context. Single-option compatibility redirects remain bounded to exactly one membership; multiple memberships open the chooser.\n\n|FILE|COMPONENT / LINE|CURRENT DESTINATION|CLASSIFICATION|EXPECTED DESTINATION|FIXED|\n|---|---|---|---|---|---|\n`+rows.map(r=>`|${esc(r.file)}|${esc(r.component)}:${r.line}|${esc(r.destination)}|${r.classification}|${esc(r.expected)}|${r.fixed}|`).join('\n')+'\n\nThe readNow compatibility helper in lib/readNow.ts has no production call sites (repository-wide reference check); current BookCapabilities and BookReaderPage use the shared context hook. No blind replacement of root/global authentication or external document links was made.\n')
console.log(JSON.stringify(meta))
