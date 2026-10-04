"""Small process-local cache of ordered identities/scores, never auth tokens."""
from collections import OrderedDict
from threading import RLock
from time import monotonic

class RankedResultCache:
    def __init__(self, ttl=180, maximum=128, clock=monotonic):
        self.ttl, self.maximum, self.clock = ttl, maximum, clock
        self.entries = OrderedDict()
        self.lock = RLock()
    def get_or_create(self, key, factory):
        with self.lock:
            now = self.clock()
            for expired in [k for k, (until, _) in self.entries.items() if until <= now]:
                del self.entries[expired]
            if key in self.entries:
                self.entries.move_to_end(key)
                return self.entries[key][1], True
            value = factory()
            self.entries[key] = (self.clock() + self.ttl, value)
            while len(self.entries) > self.maximum:
                self.entries.popitem(last=False)
            return value, False
