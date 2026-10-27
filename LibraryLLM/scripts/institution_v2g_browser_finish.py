"""Resume only the final unchanged global-page assertions after measured matrices."""
source=(ROOT/'scripts/institution_v2g_browser.py').read_text(encoding='utf8')
exec(source.split("fresh('patron');rail('/',None)")[0],globals())
prior=json.loads((REPORTS/'institution_v2g_browser.json').read_text(encoding='utf8'))
checks=prior['checks'];responsive=prior['responsive'];badges=prior['badges'];controls=prior['controls']
assert len(responsive)==36 and len(badges)==18 and len(controls)==78
exec("fresh('patron');ready('/experimental/kg')"+source.split("fresh('patron');ready('/experimental/kg')",1)[1],globals())
