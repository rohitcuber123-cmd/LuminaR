from pathlib import Path
import re

root=Path('D:/SDC/LibraryLLM'); before=root/'.scratch/platform-completion/before'
for name in ['components/AccountMenu.tsx','pages/PlatformConsole.tsx']:
    p=root/'frontend/src'/name
    s=p.read_text(encoding='utf-8').encode('cp1252').decode('utf-8')
    p.write_text(s,encoding='utf-8')
for name in ['components/AIChatWidget.tsx','components/assistant/AssistantTurn.tsx','components/RelatedBookCard.tsx','components/events/EventUI.tsx','pages/BookReaderPage.tsx','pages/KnowledgeGraphPage.tsx']:
    rel=Path('frontend/src')/name; s=(before/rel).read_text(encoding='utf-8')
    receiver='product' if name=='components/AIChatWidget.tsx' else 'context'
    s=re.sub(r'(?<!import \{ )productBookPath\(([^()\n]+)\)',lambda m:receiver+'.personalPath('+m.group(0)+')',s)
    (root/rel).write_text(s,encoding='utf-8')
p=root/'frontend/src/components/BookCarousel.tsx';s=(before/'frontend/src/components/BookCarousel.tsx').read_text(encoding='utf-8')
start=s.rindex('\n  return (')
s=s[:start]+'''\n  return <div className="product-carousel">
    <div ref={scrollRef} className="product-book-rail flex overflow-x-auto no-scrollbar scroll-smooth" style={{gap:`${gap}px`}}>{children}</div>
    {(canScrollLeft || canScrollRight) && <div className="product-rail-controls" aria-label="Book rail navigation">
      <button onClick={()=>scroll('left')} disabled={!canScrollLeft || isTransitioning} aria-label="Scroll left"><ChevronLeft size={20}/></button>
      <button onClick={()=>scroll('right')} disabled={!canScrollRight || isTransitioning} aria-label="Scroll right"><ChevronRight size={20}/></button>
    </div>}
  </div>
}
''';p.write_text(s,encoding='utf-8')
for name in ['Hero','ForYou','NewArrivals','PopularBooks','CategoryExplorer','AlsoLikeTicker']:
    p=root/f'frontend/src/components/{name}.tsx';s=p.read_text(encoding='utf-8')
    s="import { useProductContext } from '../hooks/useProductContext'\n"+s
    pos=s.index('\n',s.index('const context'))
    s=s[:pos]+"\n  const productNavigation=useProductContext()"+s[pos:]
    s=re.sub(r'to=\{(home(?:Book|Catalogue)Path\([^\n]+?\))\}',r'to={productNavigation.personalPath(\1)}',s)
    p.write_text(s,encoding='utf-8')
p=root/'frontend/src/components/Footer.tsx';s=p.read_text(encoding='utf-8').replace(": '/catalog?sort=new_arrivals'",": context.personalPath('/catalog?sort=new_arrivals')");p.write_text(s,encoding='utf-8')
p=root/'frontend/src/components/BookDiscoveryMenu.tsx';s=p.read_text(encoding='utf-8').replace('to={withPatronContext(', 'to={context.personalPath(withPatronContext(').replace('libraryId || context.libraryId)}','libraryId || context.libraryId))}');p.write_text(s,encoding='utf-8')
p=root/'frontend/src/pages/LibraryInventory.tsx';s=p.read_text(encoding='utf-8');s="import { useProductContext } from '../hooks/useProductContext'\n"+s
for marker in ['function InventoryDetails(', 'function BookForm(']:
    pos=s.index('\n',s.index(marker));s=s[:pos]+"\n  const productContext=useProductContext()"+s[pos:]
s=s.replace('href="/catalog"','href={productContext.cataloguePath}');p.write_text(s,encoding='utf-8')
p=root/'frontend/src/pages/PlatformConsole.tsx';s=p.read_text(encoding='utf-8');s="import { useProductContext } from '../hooks/useProductContext'\n"+s
for marker in ['export function PlatformOverview()', 'export function PlatformCatalogue()']:
    pos=s.index('\n',s.index(marker));s=s[:pos]+"\n  const productContext=useProductContext()"+s[pos:]
s=s.replace('to="/account/libraries?group=staff"',"to={productContext.personalPath('/account/libraries?group=staff')}")
s=s.replace("to={'/book/' + encodeURIComponent(row.work_id)}","to={productContext.personalPath('/book/' + encodeURIComponent(row.work_id))}")
p.write_text(s,encoding='utf-8')
