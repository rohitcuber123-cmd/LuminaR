"""Pytest command metadata only: never serialize queries, documents or URIs."""
import json
import os
from collections import Counter
from pathlib import Path
from pymongo import monitoring

COUNTS = Counter()


class Trace(monitoring.CommandListener):
    def started(self, event):
        command = event.command_name
        if command in {'authenticate', 'saslStart', 'saslContinue', 'hello', 'isMaster'}:
            return
        resource = event.command.get(command)
        if not isinstance(resource, str):
            resource = event.command.get('collection', '<database>')
        COUNTS[(event.database_name, resource, command)] += 1

    def succeeded(self, event):
        pass

    def failed(self, event):
        COUNTS[('<failed>', '<redacted>', event.command_name)] += 1


monitoring.register(Trace())


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get('LUMINAR_V2N_TRACE_OUTPUT')
    if path:
        Path(path).write_text(json.dumps([{'database': db, 'collection': coll, 'command': cmd, 'count': count}
                                         for (db, coll, cmd), count in sorted(COUNTS.items())], indent=2))
