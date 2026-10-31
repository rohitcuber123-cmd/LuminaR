from pathlib import Path
def main():
    out=Path('scratch/search_smart_engineering/regression');out.mkdir()
    for p in Path('scratch/search_v2c_c5er/regression_v4').glob('*.py'):
        text=p.read_text(encoding='utf8').replace('scratch.search_v2c_c5er.candidate_search_v4.query_plan','scratch.search_smart_engineering.parser').replace('scratch.search_v2c_c5er.candidate_search_v4.query_confidence','scratch.search_smart_engineering.parser')
        with (out/p.name).open('x',encoding='utf8') as f:f.write(text)
if __name__=='__main__':main()
