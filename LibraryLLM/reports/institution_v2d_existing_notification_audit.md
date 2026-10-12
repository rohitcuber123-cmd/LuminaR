# Existing notification path audit

Existing inbox is account-owned, with mark-one/read-all, current-before-resolved ordering, durable writes, globally unique dedupe keys and an existing hourly legacy-loan reminder worker. Platform messages require explicit platform authority. Legacy reservation-ready and reminder source references do not prove canonical tenancy. Part 2B/2C committed operation plans and projected audit effects exist, but have no notification outbox. Bell has no canonical item action or library label. Platform user_activity must exclude new tenant inbox content. No current legacy work_id is converted to a tenant UUID.

Baseline: `institution_v2d_baseline.json`; source copies captured before changes. Every matching production call site below is classified. Migration and QA scripts are classified separately by their dry-run/test purpose.

| File | Line | Classification | Existing path/call |
|---|---:|---|---|
| backend/main.py | 11 | GLOBAL_ACCOUNT | `from backend.services.notification_service import ensure_indexes` |
| backend/routes/notifications.py | 8 | GLOBAL_ACCOUNT | `from backend.services import notification_service as ns, admin_operation_service as ops` |
| backend/routes/notifications.py | 25 | GLOBAL_ACCOUNT | `router = APIRouter(prefix='/notifications', tags=['Notifications'], dependencies=[Depends(account)])` |
| backend/routes/notifications.py | 94 | GLOBAL_ACCOUNT | `@platform_router.post('/notifications', status_code=201)` |
| backend/routes/notifications.py | 103 | GLOBAL_ACCOUNT | `@platform_router.get('/notifications/sent')` |
| backend/services/admin_operation_service.py | 4 | GLOBAL_ACCOUNT | `from backend.services.notification_service import USER_FIELDS, normalize_dates` |
| backend/services/loan_notification_service.py | 3 | LEGACY_AMBIGUOUS | `from backend.services import notification_service as ns` |
| backend/services/loan_renewal_service.py | 5 | GLOBAL_ACCOUNT | `from backend.services.notification_service import utc, normalize_dates` |
| backend/services/loan_renewal_service.py | 6 | GLOBAL_ACCOUNT | `from backend.services.loan_notification_service import reconcile_loan_notifications` |
| backend/services/notification_service.py | 60 | LEGACY_AMBIGUOUS | `def insert_notice(user_id, kind, title, message, key, source='SYSTEM', source_ref=None, sender=None, now=None):` |
| backend/services/notification_service.py | 82 | LEGACY_AMBIGUOUS | `notice, created = insert_notice(uid, 'ADMIN_MESSAGE', title, message, key,` |
| backend/services/notification_service.py | 157 | LEGACY_AMBIGUOUS | `def scan_due(now=None, user_ids=None):` |
| backend/services/notification_service.py | 167 | LEGACY_AMBIGUOUS | `from backend.services.loan_notification_service import reconcile_current_reminders, reconcile_loan_notifications, stale_reason` |
| backend/services/notification_service.py | 192 | LEGACY_AMBIGUOUS | `_, created = insert_notice(uid, kind, {'DUE_SOON': 'Book due soon', 'DUE_TODAY': 'Book due today',` |
| backend/services/notification_service.py | 206 | LEGACY_AMBIGUOUS | `def notify_reservation_available(reservation):` |
| backend/services/notification_service.py | 207 | LEGACY_AMBIGUOUS | `return insert_notice(reservation['user_id'], 'RESERVATION_AVAILABLE', 'Reservation ready',` |
| backend/services/notification_worker.py | 5 | GLOBAL_ACCOUNT | `from backend.services.notification_service import scan_due` |
| backend/services/notification_worker.py | 28 | GLOBAL_ACCOUNT | `result = scan_due()` |
| frontend/src/components/Header.tsx | 10 | GLOBAL_ACCOUNT | `import { NotificationCenter } from './NotificationCenter'` |
| frontend/src/components/Header.tsx | 27 | GLOBAL_ACCOUNT | `{isAuthenticated && user && <NotificationCenter key={`notifications:${user.user_id ?? user.id}`} />}` |
| frontend/src/components/NotificationCenter.tsx | 5 | GLOBAL_ACCOUNT | `import { noticeDelta, type Notice } from '../lib/notifications'` |
| frontend/src/components/NotificationCenter.tsx | 9 | GLOBAL_ACCOUNT | `export function NotificationCenter() {` |
| frontend/src/components/NotificationCenter.tsx | 38 | GLOBAL_ACCOUNT | `const latest = await coreRequest<Inbox>('/notifications?limit=20', { signal: controller.signal })` |
| frontend/src/components/NotificationCenter.tsx | 43 | GLOBAL_ACCOUNT | `if (offset) page = await coreRequest<Inbox>(`/notifications?limit=20&offset=${offset}`, { signal: controller.signal })` |
| frontend/src/components/NotificationCenter.tsx | 72 | GLOBAL_ACCOUNT | `await coreRequest(id ? `/notifications/${encodeURIComponent(id)}/read` : '/notifications/read-all', { method: id ? 'PATCH' : 'POST' })` |
| frontend/src/components/events/EventMonitor.tsx | 7 | GLOBAL_ACCOUNT | `// One app-level Events subscription. NotificationCenter keeps its existing` |
| frontend/src/pages/PlatformOperations.tsx | 69 | PLATFORM | `await api('/platform/notifications', { method: 'POST', body: JSON.stringify({ recipient_user_ids: ids, title: current.title, message: current.message, request_id: current.requestId }) })` |
| frontend/src/pages/PlatformOperations.tsx | 92 | PLATFORM | `useEffect(() => { const controller = new AbortController(); void api<typeof sent>(`/platform/notifications/sent?limit=20&offset=${page * 20}`, { signal: controller.signal }).then(r => { setSent(r); setError('') }).catch(e => { if (!controller.signal.aborted) setError(e.message) }); return () => controller.abort() }, [page, revision])` |

Legacy records are preserved; UNKNOWN/AMBIGUOUS provenance requires explicit operator review. New LIBRARY_TENANT routes and journal intents are documented in the final architecture reports.
