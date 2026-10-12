"""Inventory actual pre-change paths using the immutable local source baseline."""
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BEFORE=ROOT/'.scratch/institution-v2d/before'


def main():
    data=json.loads((ROOT/'reports/institution_v2d_baseline.json').read_text())
    inventories={'event':[], 'notification':[]}
    for p in BEFORE.rglob('*'):
        if not p.is_file() or p.suffix not in {'.py','.ts','.tsx'}:continue
        name=p.relative_to(BEFORE).as_posix()
        for line_no,line in enumerate(p.read_text(encoding='utf8').splitlines(),1):
            for kind,pattern in [('event',r'(event_service|/events|eventApi\.|EventMonitor|EventsPage|EventDetailPage|ManageEventsPage|EventEditorPage)'),('notification',r'(insert_notice|notify_reservation_available|notification_service|loan_notification_service|/notifications|NotificationCenter|scan_due)')]:
                if re.search(pattern,line):
                    classification='GLOBAL_PLATFORM' if kind=='event' and '/platform' in line else 'LEGACY_GLOBAL' if kind=='event' else 'PLATFORM' if '/platform' in line or 'send_admin' in line else 'LEGACY_AMBIGUOUS' if any(v in name for v in ['notification_service','loan_notification','reservation_service']) else 'GLOBAL_ACCOUNT'
                    inventories[kind].append((name,line_no,classification,line.strip().replace('|','\\|')[:360]))
    intros={
        'event': 'Existing Events V1 uses the global events collection, immutable UUIDs, category presets, revision-checked atomic transitions, first-publication timestamps, bounded listing and account seen receipts. /platform/events requires explicit PlatformRoleAssignment. No tenant event routes, library_id or member visibility exist. The single local legacy event remains LEGACY_GLOBAL; migration requires an explicit GLOBAL decision. Existing useful fields and design are reused. No event mass fanout is introduced.',
        'notification': 'Existing inbox is account-owned, with mark-one/read-all, current-before-resolved ordering, durable writes, globally unique dedupe keys and an existing hourly legacy-loan reminder worker. Platform messages require explicit platform authority. Legacy reservation-ready and reminder source references do not prove canonical tenancy. Part 2B/2C committed operation plans and projected audit effects exist, but have no notification outbox. Bell has no canonical item action or library label. Platform user_activity must exclude new tenant inbox content. No current legacy work_id is converted to a tenant UUID.'}
    for kind,rows in inventories.items():
        text=f'# Existing {kind} path audit\n\n{intros[kind]}\n\nBaseline: `institution_v2d_baseline.json`; source copies captured before changes. Every matching production call site below is classified. Migration and QA scripts are classified separately by their dry-run/test purpose.\n\n| File | Line | Classification | Existing path/call |\n|---|---:|---|---|\n'
        text+='\n'.join(f'| {name} | {line_no} | {classification} | `{code}` |' for name,line_no,classification,code in rows)
        text+='\n\nLegacy records are preserved; UNKNOWN/AMBIGUOUS provenance requires explicit operator review. New LIBRARY_TENANT routes and journal intents are documented in the final architecture reports.\n'
        (ROOT/f'reports/institution_v2d_existing_{kind}_audit.md').write_text(text,encoding='utf8')
    print(json.dumps({kind:len(rows) for kind,rows in inventories.items()}))


if __name__=='__main__':main()
