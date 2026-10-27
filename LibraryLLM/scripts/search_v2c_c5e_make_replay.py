"""Mechanical namespace adaptation; no evaluation contract changes."""
from pathlib import Path
def main():
    text=Path('scripts/search_v2c_c5d_repair_v2_predict.py').read_text(encoding='utf8')
    text=text.replace('scratch.search_v2c_c5d_repair_v2','scratch.search_v2c_c5e')
    old="P = 'search_v2c_c5d_repair_v2_validation_' if len(sys.argv)>1 and sys.argv[1]=='validation' else 'search_v2c_c5d_repair_v2_'"
    assert old in text
    text=text.replace(old,"P = 'search_v2c_c5e_development_' if len(sys.argv)>1 and sys.argv[1]=='development' else 'search_v2c_c5e_independent_'")
    with Path('scripts/search_v2c_c5e_predict.py').open('x',encoding='utf8') as f:f.write(text)
    text=Path('scripts/search_v2c_c5d_repair_v2_score.py').read_text(encoding='utf8')
    text=text.replace('search_v2c_c5d_repair_v2_','search_v2c_c5e_development_')
    with Path('scripts/search_v2c_c5e_development_score.py').open('x',encoding='utf8') as f:f.write(text)
if __name__=='__main__':main()
