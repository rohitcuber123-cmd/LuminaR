"""Core lifecycle reminder thread: startup catch-up, then hourly; safe dedupe across workers."""
import logging
import os
from threading import Event, Thread
from backend.services.notification_service import scan_due

log = logging.getLogger('uvicorn.error')
status = {'running': False, 'last_scan': None, 'last_error_code': None}


class DueWorker:
    def __init__(self):
        self.stop_event = Event()
        self.thread = None

    def start(self):
        if os.getenv('NOTIFICATION_DUE_WORKER_ENABLED', '1') != '1':
            return
        self.thread = Thread(target=self.run, name='notification-due-worker', daemon=True)
        self.thread.start()

    def run(self):
        status['running'] = True
        try:
            interval = max(5, int(os.getenv('NOTIFICATION_DUE_CHECK_INTERVAL_MINUTES', '60'))) * 60
            while not self.stop_event.is_set():
                try:
                    result = scan_due()
                    status.update(last_scan=result, last_error_code=None)
                    log.info('notification_due_scan created=%s duplicates=%s duration_ms=%.2f',
                             result['created'], result['duplicates_skipped'], result['duration_ms'])
                except Exception:
                    # No source documents, emails, titles, tokens or messages in logs.
                    status['last_error_code'] = 'DUE_SCAN_FAILED'
                    log.error('notification_due_scan_failed')
                self.stop_event.wait(interval)
        finally:
            status['running'] = False

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
