"""Explicit real missing-author and multiple-author samples at six sizes."""
exec((ROOT/'scripts/institution_v2f1_browser.py').read_text(encoding='utf8'))
exec((ROOT/'scripts/institution_v2f1_visual_browser.py').read_text(encoding='utf8'))
saved=json.loads((REPORTS/'institution_v2f1_consolidated_covers.json').read_text())
cover_rows=saved['checks'];responsive_rows=saved['responsive']
fixtures=json.loads((REPORTS/'institution_v2f1_consolidated_fixtures.json').read_text())
local=db.institution_library_books.find_one({'library_id':fixtures['format_library'],'library_book_id':fixtures['Online']['library_book_id']})
assert not local.get('authors')
multi=db.books.find_one({'work_id':'OL15159532W'},{'title':1,'authors':1})
assert multi and 'Jeff' in str(multi['authors']) and 'Janet' in str(multi['authors'])
fresh_login('patron')
for name,path in [('missing_author',f'/libraries/{fixtures["format_library"]}/books/{local["library_book_id"]}'),('multiple_authors','/book/OL15159532W')]:
    for width,height in VIEWPORTS:cover_surface(name,path,width,height)
saved.update(checks=cover_rows,responsive=responsive_rows,explicit_missing_author=True,explicit_multiple_authors=True)
put('institution_v2f1_consolidated_covers.json',saved)
print('PASS explicit author cases; total viewport cases',len(responsive_rows),flush=True)
