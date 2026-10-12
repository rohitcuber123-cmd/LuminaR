"""Private study-model/artifact persistence, isolated from retrieval indexes."""
import hashlib
import json
import time
from uuid import uuid4
from threading import Lock, Semaphore
from concurrent.futures import Future

from fastapi import HTTPException

from rag.services import knowledge_algorithms as algorithms
from rag.services import knowledge_quiz
from rag.services import document_knowledge, knowledge_encoder
from rag.services import knowledge_quiz_evidence
from rag.services import knowledge_quiz_relations
from rag.services import knowledge_cloze, cloze_grading

TYPES = {'key-concepts': 'KEY_CONCEPTS', 'summary': 'EXTRACTIVE_SUMMARY',
         'flashcards': 'FLASHCARDS', 'mindmap': 'MIND_MAP', 'quiz': 'QUIZ'}


class KnowledgeArtifacts:
    def __init__(self, documents, encoder=None):
        self.documents = documents
        self.encoder = encoder or knowledge_encoder.encode
        self._lock = Lock()
        self._jobs = {}
        self._owners = set()
        self._capacity = Semaphore(3)
        with documents.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS knowledge_artifacts (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                owner TEXT NOT NULL, type TEXT NOT NULL, cache_key TEXT NOT NULL,
                payload TEXT NOT NULL, updated REAL NOT NULL,
                UNIQUE(document_id, owner, type, cache_key))''')
            db.execute('''CREATE TABLE IF NOT EXISTS document_knowledge (
                document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
                owner TEXT NOT NULL, revision TEXT NOT NULL, version TEXT NOT NULL, payload TEXT NOT NULL)''')

    def _knowledge(self, row, chunks, revision, user):
        with self.documents.db() as db:
            self._active(db, row['id'], user)
            cached = db.execute('SELECT payload FROM document_knowledge WHERE document_id=? AND owner=? AND revision=? AND version=?',
                                (row['id'], row['owner'], revision, document_knowledge.VERSION)).fetchone()
        if cached:
            model = document_knowledge.DocumentKnowledgeModel(**json.loads(cached['payload']))
            if (model.quiz_evidence_version != knowledge_quiz_evidence.VERSION
                    or model.quiz_relation_version != knowledge_quiz_relations.VERSION
                    or not model.quiz_relation_semantic_prepared):
                knowledge_quiz_evidence.attach(model, self.encoder)
                knowledge_quiz_relations.attach(model)
                with self.documents.db() as db:
                    self._active(db, row['id'], user)
                    db.execute('UPDATE document_knowledge SET payload=? WHERE document_id=? AND owner=?',
                               (json.dumps(model.payload()), row['id'], row['owner']))
            return model, True
        model = document_knowledge.build(self._parse(chunks), self.encoder)
        knowledge_quiz_evidence.attach(model, self.encoder)
        knowledge_quiz_relations.attach(model)
        with self.documents.db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._active(db, row['id'], user)
            db.execute('INSERT OR REPLACE INTO document_knowledge VALUES (?,?,?,?,?)',
                       (row['id'], row['owner'], revision, model.version, json.dumps(model.payload())))
        return model, False

    def prepare_cloze_grading(self):
        if self.encoder is knowledge_encoder.encode:
            knowledge_encoder.prepare()

    @staticmethod
    def _parse(raw):
        try:
            chunks = json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise HTTPException(409, 'Document text is unavailable. Restore or upload the PDF again.') from error
        if not isinstance(chunks, list) or any(not isinstance(c, dict) or not isinstance(c.get('chunk_id'), str)
                or not isinstance(c.get('text'), str) for c in chunks):
            raise HTTPException(409, 'Document text is unavailable. Restore or upload the PDF again.')
        return chunks

    def _source(self, document_id, user, parse=True):
        row = self.documents.owned(document_id, user)
        try:
            path = self.documents.directory(document_id) / 'chunks.json'
            if path.stat().st_size > 64 * 1024 * 1024:
                raise HTTPException(413, 'This document is too large for Knowledge Tools.')
            raw = path.read_bytes()
            chunks = self._parse(raw) if parse else raw
        except (OSError, ValueError):
            raise HTTPException(409, 'Document text is unavailable. Restore or upload the PDF again.')
        return row, chunks, hashlib.sha256(raw).hexdigest()

    def _active(self, db, document_id, user):
        owner, sid = self.documents.identity(user)
        row = db.execute("SELECT id FROM documents WHERE id=? AND owner=? AND sid=? AND state='ACTIVE' AND expires>?",
                         (document_id, owner, sid, time.time())).fetchone()
        if row is None:
            raise HTTPException(404, 'Document not found.')

    def generate(self, document_id, slug, user, mode='quick', question_types=None, question_count=knowledge_quiz.DEFAULT_COUNT):
        # Owner/session checks happen before work admission, including joined requests.
        row = self.documents.owned(document_id, user)
        owner = row['owner']
        job_key = (owner, row['sid'], document_id, slug, mode, tuple(sorted(question_types or ())), question_count)
        leader = False
        with self._lock:
            future = self._jobs.get(job_key)
            if future is None:
                if owner in self._owners or not self._capacity.acquire(blocking=False):
                    raise HTTPException(429, 'Knowledge Tools is busy. Please retry shortly.')
                future = Future()
                self._jobs[job_key] = future
                self._owners.add(owner)
                leader = True
        if not leader:
            try:
                result = future.result(timeout=25)
            except TimeoutError:
                raise HTTPException(429, 'This artifact is still being prepared. Please retry shortly.')
            self.documents.owned(document_id, user)
            return {**result, 'cached': True}
        try:
            result = self._generate(document_id, slug, user, mode, question_types, question_count)
            future.set_result(result)
            return result
        except BaseException as error:
            future.set_exception(error)
            raise
        finally:
            with self._lock:
                self._jobs.pop(job_key, None)
                self._owners.discard(owner)
                self._capacity.release()

    def _generate(self, document_id, slug, user, mode, question_types, question_count):
        started = time.perf_counter()
        row, chunks, revision = self._source(document_id, user, parse=False)
        if slug not in TYPES:
            raise HTTPException(422, 'Unknown artifact type.')
        kind = TYPES[slug]
        options = {'mode': mode} if kind == 'EXTRACTIVE_SUMMARY' else {}
        if kind == 'QUIZ':
            try:
                options = knowledge_quiz.quiz_options(question_types, question_count)
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
        version = knowledge_quiz.VERSION if kind == 'QUIZ' else algorithms.VERSION
        scope = {'type': 'document'}
        identity = [revision, kind, scope, options, version, document_knowledge.VERSION]
        if kind == 'QUIZ':
            identity.append(knowledge_quiz_relations.VERSION)
            if 'fill_blank' in options['questionTypes']:
                identity.append(knowledge_cloze.VERSION)
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        with self.documents.db() as db:
            self._active(db, document_id, user)
            cached = db.execute('SELECT payload FROM knowledge_artifacts WHERE document_id=? AND owner=? AND type=? AND cache_key=?',
                                (document_id, row['owner'], kind, key)).fetchone()
        if cached:
            return {'artifact': json.loads(cached['payload']), 'cached': True}
        model, knowledge_cached = self._knowledge(row, chunks, revision, user)
        content = algorithms.generate(kind, [], json.loads(row['metadata'])['filename'], options, model)
        references = set()
        def collect(value):
            if isinstance(value, dict):
                references.update(value.get('sourceChunkIds', []))
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)
        collect(content)
        now = time.time()
        artifact = {'id': 'artifact_' + uuid4().hex, 'userId': row['owner'], 'documentId': document_id,
                    'type': kind, 'scope': scope, 'generator': 'document-knowledge-v3', 'generatorVersion': version,
                    'options': options, 'sourceRevision': revision, 'content': content,
                    'sourceChunkIds': sorted(references), 'createdAt': now, 'updatedAt': now,
                    'analysis': {'sampled': bool(model.metrics.get('sampled')),
                                 'chunkLimit': algorithms.MAX_CHUNKS, 'sentenceLimit': algorithms.MAX_SENTENCES,
                                 'knowledgeCached': knowledge_cached, 'knowledgeVersion': model.version,
                                 'metrics': {**model.metrics,
                                     'embedding_calls': 0 if knowledge_cached else model.metrics.get('embedding_calls', 0),
                                     'embedding_ms': 0 if knowledge_cached else model.metrics.get('embedding_ms', 0),
                                     'knowledge_model_ms': 0 if knowledge_cached else model.metrics['knowledge_model_ms'],
                                     'artifact_generation_ms': round((time.perf_counter()-started)*1000, 2)}}}
        if kind == 'QUIZ':
            artifact['analysis']['quizRelationVersion'] = knowledge_quiz_relations.VERSION
            if 'fill_blank' in options['questionTypes']:
                artifact['analysis']['clozeVersion'] = knowledge_cloze.VERSION
        with self.documents.db() as db:
            # Serialize publication with deletion/logout; never resurrect derived private content.
            db.execute('BEGIN IMMEDIATE')
            self._active(db, document_id, user)
            existing = db.execute('SELECT payload FROM knowledge_artifacts WHERE document_id=? AND owner=? AND type=? AND cache_key=?',
                                  (document_id, row['owner'], kind, key)).fetchone()
            if existing:
                return {'artifact': json.loads(existing['payload']), 'cached': True}
            # Bound historical versions while retaining quick and detailed summaries.
            for old in db.execute('SELECT id,payload FROM knowledge_artifacts WHERE document_id=? AND owner=? AND type=?',
                                  (document_id, row['owner'], kind)).fetchall():
                if json.loads(old['payload'])['options'] == options:
                    db.execute('DELETE FROM knowledge_artifacts WHERE id=?', (old['id'],))
            db.execute('INSERT INTO knowledge_artifacts VALUES (?,?,?,?,?,?,?)',
                       (artifact['id'], document_id, row['owner'], kind, key, json.dumps(artifact), now))
        return {'artifact': artifact, 'cached': False}

    def list(self, document_id, user):
        row, _, revision = self._source(document_id, user, parse=False)
        with self.documents.db() as db:
            self._active(db, document_id, user)
            items = db.execute('SELECT payload FROM knowledge_artifacts WHERE document_id=? AND owner=? ORDER BY updated DESC',
                               (document_id, row['owner'])).fetchall()
        artifacts = [json.loads(item['payload']) for item in items]
        return {'artifacts': [a for a in artifacts if a['sourceRevision'] == revision and a.get('analysis', {}).get('knowledgeVersion') == document_knowledge.VERSION
            and (a['type'] != 'QUIZ' or a.get('analysis', {}).get('quizRelationVersion') == knowledge_quiz_relations.VERSION) and a['generatorVersion'] in
            ((knowledge_quiz.VERSION,) if a['type'] == 'QUIZ' else (algorithms.VERSION,))
            and ('fill_blank' not in a.get('options',{}).get('questionTypes',[]) or a.get('analysis',{}).get('clozeVersion')==knowledge_cloze.VERSION)]}

    def grade_cloze(self, document_id, artifact_id, item_id, answer, user):
        artifact = self.get(document_id, artifact_id, user)
        item = next((q for q in artifact['content'].get('questions',[]) if q['id']==item_id and q['type']=='fill_blank'), None)
        if artifact['type']!='QUIZ' or item is None:
            raise HTTPException(404, 'Cloze item not found.')
        if not knowledge_cloze.validate(item):
            raise HTTPException(409, 'Generate this quiz again before checking answers.')
        try:
            result = cloze_grading.grade(item, answer, self.encoder)
        except (RuntimeError, ValueError, TimeoutError) as error:
            raise HTTPException(503, 'Answer checking is temporarily unavailable. Keep your answer and retry.') from error
        with self.documents.db() as db:
            self._active(db,document_id,user)
            if not db.execute('SELECT id FROM knowledge_artifacts WHERE id=? AND document_id=? AND owner=?',
                    (artifact_id,document_id,str(user['sub']))).fetchone():
                raise HTTPException(404, 'Artifact not found.')
        return result

    def get(self, document_id, artifact_id, user):
        for artifact in self.list(document_id, user)['artifacts']:
            if artifact['id'] == artifact_id:
                return artifact
        raise HTTPException(404, 'Artifact not found or no longer current. Generate it again.')

    def delete(self, document_id, artifact_id, user):
        self.documents.owned(document_id, user)
        with self.documents.db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._active(db, document_id, user)
            removed = db.execute('DELETE FROM knowledge_artifacts WHERE id=? AND document_id=? AND owner=?',
                                (artifact_id, document_id, str(user['sub']))).rowcount
        if not removed:
            raise HTTPException(404, 'Artifact not found.')
        return {'removed': True}

    def source(self, document_id, chunk_id, user):
        row, chunks, _ = self._source(document_id, user)
        for chunk in chunks:
            if chunk['chunk_id'] == chunk_id:
                self.documents.owned(document_id, user)
                return {'chunkId': chunk_id, 'documentId': document_id, 'filename': json.loads(row['metadata'])['filename'],
                        'text': chunk['text'][:12000], **algorithms.provenance(chunk)}
        raise HTTPException(404, 'Source chunk not found.')
