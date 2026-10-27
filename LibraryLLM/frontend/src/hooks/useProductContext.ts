import { useLocation } from 'react-router-dom'
import { resolveAuthorizedProductContext, resolveProductHomeDestination, productCatalogueDestination, productNewArrivalsDestination, productSearchDestination, productEventsPath, withProductContext } from '../lib/productContext'
import { useAuthStore } from '../store/useAuthStore'
import { useInstitutionStore } from '../store/useInstitutionStore'
import { libraryRole } from '../lib/libraryWorkspace'
import { platformAdmin, usePlatformStore } from '../store/usePlatformStore'
export function useProductContext() {
  const location=useLocation(),token=useAuthStore(s=>s.token),state=useInstitutionStore()
  const platform=usePlatformStore()
  const memberships=state.session===token && token && !state.loading ? state.libraries.flatMap(l=>libraryRole(l)?[{library_id:l.library_id,role:libraryRole(l)!}]:[]):[]
  const context=resolveAuthorizedProductContext(location.pathname,location.search,memberships,platformAdmin(platform,token))
  const libraryId=context.kind==='PATRON_LIBRARY' ? context.libraryId:null
  return { kind:context.kind, routeContext:context, libraryId, staffLibraryId:context.kind==='STAFF_LIBRARY'?context.libraryId:null,
    homePath:resolveProductHomeDestination(context),eventsPath:productEventsPath(context),cataloguePath:productCatalogueDestination(context),newArrivalsPath:productNewArrivalsDestination(context),searchPath:(query:string)=>productSearchDestination(context,query),
    personalPath:(path:string)=>withProductContext(path,context) }
}
