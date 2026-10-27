# Frontend V2 baseline
The workspace already contained extensive uncommitted work. The task-start snapshot hashes 169 frontend files and 212 protected Python files. It also records 50 protected artifact references. `frontend_v2_before.png` captures the recovered catalogue before this redesign.
The existing shared BookCard stacked all personal actions at full width, duplicated View Details, and changed height with capabilities. Cards lacked a common action slot. Rail movement assumed 180px cards and four-card pages. Route changes used a blanket scroll-to-top hook. Prior frontend regression coverage was 903 tests.
Services use the existing MongoDB database. No database path or credentials were reset. This task did not resume V2C-C.2 or Part 2I.
