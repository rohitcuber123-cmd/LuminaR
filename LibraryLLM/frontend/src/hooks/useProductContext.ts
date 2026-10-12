import { useLocation } from 'react-router-dom'
import { resolveProductContext, resolveProductHomeDestination, productCatalogueDestination, productNewArrivalsDestination, productSearchDestination, productEventsPath, withProductContext } from '../lib/productContext'
import { useAuthStore } from '../store/useAuthStore'
import { useInstitutionStore } from '../store/useInstitutionStore'
import { libraryRole } from '../lib/libraryWorkspace'
export function useProductContext() {
  const location=useLocation(),token=useAuthStore(s=>s.token),state=useInstitutionStore()
  const route=resolveProductContext(location.pathname,location.search)
  const membership=state.session===token && token ? state.libraries.find(l=>l.library_id===route.libraryId) : null
  const context=resolveProductContext(location.pathname,location.search,libraryRole(membership))
  const libraryId=context.kind==='PATRON_LIBRARY' ? context.libraryId:null
  return { kind:context.kind, routeContext:context, libraryId, staffLibraryId:context.kind==='STAFF_LIBRARY'?context.libraryId:null,
    homePath:resolveProductHomeDestination(context),eventsPath:productEventsPath(context),cataloguePath:productCatalogueDestination(context),newArrivalsPath:productNewArrivalsDestination(context),searchPath:(query:string)=>productSearchDestination(context,query),
    personalPath:(path:string)=>withProductContext(path,context) }
}
