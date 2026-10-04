"""Revalidate full catalogue fields without overwriting KG31 evidence."""
from pathlib import Path
source=Path(__file__).resolve().parent/'audit_kg_ontology.py'
text=source.read_text(encoding='utf-8').replace('kg_ontology_enrichment_audit.json','kg_v2_metadata_audit.json').replace('kg31_audit.sqlite','kg_productization_metadata_degrees.sqlite').replace('kg31_audit_progress.json','kg_productization_metadata_progress.json').replace('kg31_baseline.json','kg_productization_graph_baseline.json')
exec(compile(text,str(source),'exec'),{'__name__':'__main__','__file__':str(source)})
