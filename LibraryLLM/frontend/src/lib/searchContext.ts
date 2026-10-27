/** Only a temporary identifier is stored here. Plans remain on the authorized server. */
export type SearchScope = {libraryId?:string;staff?:boolean}
const prefix='luminar_search_context:'
function account() {
  try {
    const user=JSON.parse(localStorage.getItem('luminar_user') || 'null')
    const token=localStorage.getItem('luminar_token') || ''
    let login='legacy'
    try {login=JSON.parse(atob(token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))).sid || login} catch { /* fixture or legacy token */ }
    return `${user?.user_id ?? user?.id ?? 'anonymous'}:${login}`
  } catch {return 'anonymous'}
}
export function contextKey(scope:SearchScope={}) {return prefix+account()+':'+(scope.libraryId?`${scope.libraryId}:${scope.staff?'STAFF':'PATRON'}`:'GLOBAL')}
export function searchContext(scope:SearchScope={}) {
  const key=contextKey(scope)
  try {
    const stored=JSON.parse(sessionStorage.getItem(key) || 'null')
    if(stored?.id && stored.expires>Date.now())return stored as {id:string;active:boolean;expires:number}
  } catch { /* expired or unsupported storage */ }
  const value={id:crypto.randomUUID(),active:false,expires:Date.now()+30*60*1000}
  sessionStorage.setItem(key,JSON.stringify(value));return value
}
export function rememberSearch(scope:SearchScope,session?:{active:boolean;expires_at:string}|null) {
  if(!session)return
  const value=searchContext(scope)
  sessionStorage.setItem(contextKey(scope),JSON.stringify({...value,active:session.active,expires:Date.parse(session.expires_at)}))
}
export function forgetSearch(scope:SearchScope={}) {sessionStorage.removeItem(contextKey(scope))}
export function clearSearchContexts() {
  for(let i=sessionStorage.length-1;i>=0;i--){const key=sessionStorage.key(i);if(key?.startsWith(prefix))sessionStorage.removeItem(key)}
}
function preferenceKey(){return 'luminar_personalized_search:'+account().split(':')[0]}
export function personalizedSearch(){return localStorage.getItem(preferenceKey())==='true'}
export function setPersonalizedSearch(value:boolean){localStorage.setItem(preferenceKey(),String(value))}
