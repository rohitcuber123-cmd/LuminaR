import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/useAuthStore'
import { useInstitutionStore } from '../store/useInstitutionStore'
import { platformAdmin, usePlatformStore } from '../store/usePlatformStore'
import { libraryRole } from '../lib/libraryWorkspace'
import { resolveAuthorizedProductContext, withProductContext } from '../lib/productContext'
import { LIBRARY_ACCESS_DENIED } from '../lib/institutions'

/** Applies to every layout, including personal pages and auth transitions. */
export function ProductSessionBoundary() {
  const location=useLocation(),navigate=useNavigate(),auth=useAuthStore(),state=useInstitutionStore(),platform=usePlatformStore()
  const previous=useRef({token:auth.token,owner:auth.user?.email || null})
  const canUsePlatform=platformAdmin(platform,auth.token)
  useEffect(()=>{
    const denied=(event:Event)=>{
      const detail=(event as CustomEvent<{library_id:string;session:string|null}>).detail
      if(detail?.session && detail.session===useAuthStore.getState().token && detail.session===useInstitutionStore.getState().session)
        useInstitutionStore.getState().forgetLibrary(detail.library_id)
    }
    window.addEventListener(LIBRARY_ACCESS_DENIED,denied)
    return ()=>window.removeEventListener(LIBRARY_ACCESS_DENIED,denied)
  },[])
  useEffect(()=>{
    const prior=previous.current,owner=auth.user?.email || null,original=location.pathname+location.search+location.hash
    const tenant=/^\/(?:staff\/libraries|libraries)\/[^/]+/.test(location.pathname) && location.pathname!=='/libraries/register'
    const changed=prior.token!==auth.token || !!owner && !!prior.owner && owner!==prior.owner
    previous.current={token:auth.token,owner:owner || prior.owner}
    if(changed && prior.token) {
      const clean=tenant ? auth.token ? '/account/continue':'/login' : withProductContext(original,{kind:'GLOBAL',libraryId:null})
      if(clean!==original)navigate(clean,{replace:true})
      return
    }
    if(auth.token && (state.session!==auth.token || state.loading || platform.session!==auth.token || platform.loading))return
    const memberships=state.session===auth.token && auth.token ? state.libraries.flatMap(l=>libraryRole(l)?[{library_id:l.library_id,role:libraryRole(l)!}]:[]):[]
    const context=resolveAuthorizedProductContext(location.pathname,location.search,memberships,canUsePlatform)
    const clean=withProductContext(original,context)
    if(clean!==original)navigate(clean,{replace:true})
  },[auth.token,auth.user?.email,state.session,state.loading,state.libraries,platform.session,platform.loading,canUsePlatform,location.pathname,location.search,location.hash,navigate])
  return null
}
