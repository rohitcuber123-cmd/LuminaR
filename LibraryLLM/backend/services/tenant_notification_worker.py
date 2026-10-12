"""Existing core lifecycle thread pattern, dedicated to committed tenant outbox."""
import logging
import os
from threading import Event, Thread
from backend.services.tenant_notification_service import materialize

log = logging.getLogger('uvicorn.error')
status = {'running': False, 'last_scan': None, 'last_error_code': None}


class TenantNotificationWorker:
    def __init__(self):
        self.stop_event = Event()
        self.thread = None

    def start(self):
        if os.getenv('NOTIFICATION_OUTBOX_WORKER_ENABLED', '1') != '1':
            return
        self.thread = Thread(target=self.run, name='tenant-notification-outbox', daemon=True)
        self.thread.start()

    def run(self):
        status['running'] = True
        try:
            interval = min(max(int(os.getenv('NOTIFICATION_OUTBOX_INTERVAL_SECONDS', '5')), 1), 300)
            while not self.stop_event.is_set():
                try:
                    result = materialize()
                    status.update(last_scan=result, last_error_code='DELIVERY_FAILED' if result['failed'] else None)
                    if result['failed']:
                        log.error('tenant_notification_delivery_failed count=%s', result['failed'])
                except Exception:
                    status['last_error_code'] = 'OUTBOX_SCAN_FAILED'
                    log.error('tenant_notification_outbox_scan_failed')
                self.stop_event.wait(interval)
        finally:
            status['running'] = False

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
