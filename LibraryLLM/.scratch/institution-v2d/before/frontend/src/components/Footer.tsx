import { Link } from 'react-router-dom'
import { BookOpen } from 'lucide-react'
import { useProductContext } from '../hooks/useProductContext'
export function Footer() {
  const context=useProductContext()
  const links=[{label:'Catalog',to:context.cataloguePath},{label:'New Arrivals',to:context.libraryId ? '/libraries/'+context.libraryId+'/new-arrivals' : context.personalPath('/catalog?sort=new_arrivals')},{label:'Reading List',to:context.personalPath('/reading-list')},{label:'My Libraries',to:context.personalPath('/account/libraries')},{label:'Events & Announcements',to:context.personalPath('/events')},{label:'Know More',to:context.personalPath('/llm')}]
  return <footer id="about" className="border-t border-line bg-ink text-paper/80 px-6 py-16 md:px-10"><div className="mx-auto max-w-[90rem] grid gap-10 md:grid-cols-2"><div><Link to={context.homePath} aria-label="LuminaR home" className="inline-flex items-center gap-2"><BookOpen size={20} className="text-brand" /><span className="font-display text-xl text-paper">LuminaR</span></Link><p className="mt-4 max-w-md text-sm leading-relaxed">Discover books, save your next reads, and explore your library’s collection with LuminaR.</p></div><nav aria-label="Footer navigation" className="grid grid-cols-2 gap-4">{links.map(link=><Link key={link.label} to={link.to} className="text-sm hover:underline">{link.label}</Link>)}</nav></div></footer>
}
