"""Small per-process limit; shared infrastructure is a deployment concern."""
from collections import OrderedDict, deque
from threading import Lock
from time import monotonic
from fastapi import HTTPException, Request

class AuthRateLimiter:
    def __init__(self, limit=20, window=60):
        self.limit, self.window = limit, window
        self.entries = OrderedDict()
        self.lock = Lock()

    def check(self, key):
        now = monotonic()
        with self.lock:
            queue = self.entries.setdefault(key, deque())
            self.entries.move_to_end(key)
            while queue and queue[0] <= now - self.window: queue.popleft()
            if len(queue) >= self.limit:
                raise HTTPException(429, 'Too many authentication attempts. Please try again shortly.', headers={'Retry-After':str(self.window)})
            queue.append(now)
            while len(self.entries) > 4096: self.entries.popitem(last=False)

limiter = AuthRateLimiter()

def limit_auth_attempts(request: Request):
    # Do not trust client-supplied forwarding headers.
    limiter.check(request.client.host if request.client else 'unknown')
