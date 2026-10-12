import { useLocation } from 'react-router-dom'
import { productLibraryId, productHomePath, productCataloguePath, withPatronContext } from '../lib/productContext'
export function useProductContext() {
  const location = useLocation(), libraryId = productLibraryId(location.pathname, location.search)
  return { libraryId, homePath: productHomePath(libraryId), cataloguePath: productCataloguePath(libraryId),
    personalPath: (path: string) => withPatronContext(path, libraryId) }
}
