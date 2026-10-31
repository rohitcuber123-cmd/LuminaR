"""Convert search_arch9_root_cause_matrix.json into a comprehensive markdown deliverable."""
import json
from pathlib import Path

matrix = json.loads(Path('reports/search_arch9_root_cause_matrix.json').read_text(encoding='utf-8'))

lines = []
lines.append('# LuminaR V8 Generalization Failure: Root-Cause Matrix (All 205 Cases across 42 Families)')
lines.append('')
lines.append('## 1. Executive Summary')
lines.append(f"- Total Cases Analyzed: {matrix['total_cases']}")
lines.append(f"- Total Linguistic Families: {matrix['total_families']}")
lines.append(f"- Failed Cases in V8 Primary: {matrix['total_failed_cases']} / 205")
lines.append('')
lines.append('### Breakdown by First Incorrect Pipeline Stage:')
for stage, count in sorted(matrix['stage_summary'].items(), key=lambda x: -x[1]):
    lines.append(f"- **{stage}**: {count} cases")
lines.append('')
lines.append('### Breakdown by Fault Architecture Layer:')
for layer, count in sorted(matrix['fault_layer_summary'].items(), key=lambda x: -x[1]):
    lines.append(f"- **{layer.title()} Layer**: {count} cases")
lines.append('')
lines.append('---')
lines.append('')
lines.append('## 2. 42-Family Architectural Breakdown')
lines.append('')
lines.append('| Family ID | Total | Failed | Primary Stage | Primary Layer | Representative Query | Architectural Remedy |')
lines.append('|---|---|---|---|---|---|---|')

for fam_id, data in sorted(matrix['families'].items()):
    rep_q = data['representative_query'].replace('|', '/').replace('\n', ' ')
    if len(rep_q) > 60:
        rep_q = rep_q[:57] + '...'
    remedy = data['architectural_remedies'][0] if data['architectural_remedies'] else 'N/A'
    if len(remedy) > 70:
        remedy = remedy[:67] + '...'
    lines.append(f"| `{fam_id}` | {data['total_cases']} | {data['failed_cases']} | {data['primary_stage']} | {data['primary_fault_layer']} | {rep_q} | {remedy} |")

lines.append('')
lines.append('---')
lines.append('## 3. Detailed Family Profiles')
lines.append('')
for fam_id, data in sorted(matrix['families'].items()):
    lines.append(f"### Family: `{fam_id}`")
    lines.append(f"- **Cases**: {data['total_cases']} (Failed: {data['failed_cases']})")
    lines.append(f"- **Primary Stage**: {data['primary_stage']}")
    lines.append(f"- **Fault Layer**: {data['primary_fault_layer']}")
    lines.append(f"- **Representative Query**: `{data['representative_query']}`")
    lines.append(f"- **Semantic Justification**: {data['semantic_justification']}")
    if data['capability_limitations']:
        lines.append(f"- **Capability Limitation**: {data['capability_limitations'][0]}")
    lines.append("- **Architectural Remedy**:")
    for rem in data['architectural_remedies']:
        lines.append(f"  - {rem}")
    lines.append(f"- **Case IDs**: `{data['case_ids']}`")
    lines.append('')

Path('reports/search_arch9_root_cause_matrix.md').write_text('\n'.join(lines), encoding='utf-8')
print('Wrote reports/search_arch9_root_cause_matrix.md')
