import { GlobalCatalogue } from '../components/GlobalCatalogue'
import { Navigate } from 'react-router-dom'
import { useProductContext } from '../hooks/useProductContext'
export function CatalogPage() {
  const context=useProductContext()
  return context.kind==='STAFF_LIBRARY' ? <Navigate to={context.cataloguePath} replace /> : <GlobalCatalogue />
}
