from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace(path, old, new):
    target = ROOT / path
    content = target.read_text(encoding='utf-8')
    assert old in content, (path, old[:100])
    target.write_text(content.replace(old, new), encoding='utf-8')

replace('frontend/src/pages/LibraryAssets.tsx', "staff ? staffPath(libraryId, 'inventory') : patronPath(libraryId, `books/${asset.library_book_id}`)", 'libraryBookPath(libraryId, asset.library_book_id, staff)')
replace('frontend/src/pages/LibraryAssets.tsx', "staff ? 'Open library inventory' : 'View linked book'", "'View linked book'")
replace('frontend/src/pages/LibraryCatalogue.tsx', 'patronPath,workspacePath,staffPath', 'workspacePath,staffPath')
replace('frontend/src/pages/LibraryInventory.tsx', "import { catalogueChanged }", "import { LibraryBookTitleLink } from '../components/LibraryBookTitleLink'\nimport { staffPath } from '../lib/libraryWorkspace'\nimport { catalogueChanged }")
replace('frontend/src/pages/LibraryInventory.tsx', 'const navigate=useNavigate()', '''const navigate=useNavigate()
  const [params, setParams] = useSearchParams()
  const search = params.get('search') || ''
  const kind = ['all', 'global', 'local', 'review'].includes(params.get('kind') || '') ? params.get('kind')! : 'all'
  const state = ['active', 'withdrawn', 'all'].includes(params.get('state') || '') ? params.get('state')! : 'active'
  const formatFilter = ['PHYSICAL_ONLY', 'DIGITAL_ONLY', 'PHYSICAL_AND_DIGITAL'].includes(params.get('format') || '') ? params.get('format')! : 'all'
  const page = Math.min(50000, Math.max(0, Number.parseInt(params.get('page') || '0', 10) || 0))
  function updateQuery(changes: Record<string, string>, resetPage = true) {
    const next = new URLSearchParams(params)
    next.delete('action')
    for (const [name, value] of Object.entries(changes)) {
      if (value) next.set(name, value); else next.delete(name)
    }
    if (resetPage) next.delete('page')
    setParams(next, {replace: true})
  }
  const inventoryReturnTo = staffPath(libraryId, 'inventory') + (params.toString() ? '?' + params.toString() : '')''')
replace('frontend/src/pages/LibraryInventory.tsx', "const [draft, setDraft] = useState(initialSearch), [search, setSearch] = useState(initialSearch), [kind, setKind] = useState('all'), [state, setState] = useState('active'), [page, setPage] = useState(0), [revision, setRevision] = useState(0)", 'const [draft, setDraft] = useState(initialSearch), [revision, setRevision] = useState(0)')
replace('frontend/src/pages/LibraryInventory.tsx', "  const [formatFilter, setFormatFilter] = useState('all')\n", '')
replace('frontend/src/pages/LibraryInventory.tsx', 'setSearch(draft); setPage(0)', "updateQuery({search: draft})")
replace('frontend/src/pages/LibraryInventory.tsx', 'setKind(e.target.value); setPage(0)', "updateQuery({kind: e.target.value})")
replace('frontend/src/pages/LibraryInventory.tsx', 'setState(e.target.value); setPage(0)', "updateQuery({state: e.target.value})")
replace('frontend/src/pages/LibraryInventory.tsx', 'setFormatFilter(e.target.value); setPage(0)', "updateQuery({format: e.target.value})")
replace('frontend/src/pages/LibraryInventory.tsx', "setDraft(''); setSearch(''); setKind('all'); setState('active'); setPage(0)", "setDraft(''); updateQuery({search: '', kind: '', state: '', format: ''})")
replace('frontend/src/pages/LibraryInventory.tsx', '<h2>{row.title}</h2>', '<h2><LibraryBookTitleLink libraryId={libraryId} bookId={row.library_book_id} staff={staff} title={row.title} state={staff ? {inventoryReturnTo} : undefined} /></h2>')
replace('frontend/src/pages/LibraryInventory.tsx', 'setPage(p => p - 1)', "updateQuery({page: String(page - 1)}, false)")
replace('frontend/src/pages/LibraryInventory.tsx', 'setPage(p => p + 1)', "updateQuery({page: String(page + 1)}, false)")
for path in ['frontend/src/pages/LibraryCirculation.tsx', 'frontend/src/pages/LibraryReservationsFees.tsx', 'frontend/src/pages/LibraryAnalyticsPage.tsx']:
    target = ROOT / path
    content = target.read_text(encoding='utf-8')
    content = "import { LibraryBookTitleLink } from '../components/LibraryBookTitleLink'\n" + content
    if path.endswith('LibraryCirculation.tsx'):
        content = content.replace('<h3>{row.title}</h3>', '<h3><LibraryBookTitleLink libraryId={libraryId} bookId={row.library_book_id} staff={staff} title={row.title} /></h3>')
    elif path.endswith('LibraryReservationsFees.tsx'):
        content = content.replace('<h3>{row.title}</h3>', '<h3><LibraryBookTitleLink libraryId={libraryId} bookId={row.library_book_id} staff={staff} title={row.title} /></h3>')
    else:
        content = content.replace('<PopularBooks rows={data.popular_books} />', '<PopularBooks libraryId={libraryId} rows={data.popular_books} />')
        content = content.replace("function PopularBooks({ rows }: { rows: LibraryAnalytics['popular_books'] })", "function PopularBooks({ rows, libraryId }: { rows: LibraryAnalytics['popular_books']; libraryId: string })")
        content = content.replace('<th scope="row">{row.title}', '<th scope="row"><LibraryBookTitleLink libraryId={libraryId} bookId={row.library_book_id} staff title={row.title} />')
    target.write_text(content, encoding='utf-8')
