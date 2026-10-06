"""Private-document artifact persistence. Never loads a model or vector index."""
import hashlib
import json
import time
from uuid import uuid4

from fastapi import HTTPException

from rag.services import knowledge_algorithms as algorithms
from rag.services import knowledge_quiz

TYPES = {'key-concepts': 'KEY_CONCEPTS', 'summary': 'EXTRACTIVE_SUMMARY',
         'flashcards': 'FLASHCARDS', 'mindmap': 'MIND_MAP', 'quiz': 'QUIZ'}


class KnowledgeArtifacts:
    def __init__(self, documents):
        self.documents = documents
        with documents.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS knowledge_artifacts (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                owner TEXT NOT NULL, type TEXT NOT NULL, cache_key TEXT NOT NULL,
                payload TEXT NOT NULL, updated REAL NOT NULL,
                UNIQUE(document_id, owner, type, cache_key))''')

    def _source(self, document_id, user):
        row = self.documents.owned(document_id, user)
        try:
            path = self.documents.directory(document_id) / 'chunks.json'
            if path.stat().st_size > 64 * 1024 * 1024:
                raise HTTPException(413, 'This document is too large for Knowledge Tools.')
            raw = path.read_bytes()
            chunks = json.loads(raw)
            if not isinstance(chunks, list) or any(not isinstance(c, dict) or not isinstance(c.get('chunk_id'), str)
                    or not isinstance(c.get('text'), str) for c in chunks):
                raise ValueError('Invalid source')
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
        row, chunks, revision = self._source(document_id, user)
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
        key = hashlib.sha256(json.dumps([revision, kind, scope, options, version], sort_keys=True).encode()).hexdigest()
        with self.documents.db() as db:
            self._active(db, document_id, user)
            cached = db.execute('SELECT payload FROM knowledge_artifacts WHERE document_id=? AND owner=? AND type=? AND cache_key=?',
                                (document_id, row['owner'], kind, key)).fetchone()
        if cached:
            return {'artifact': json.loads(cached['payload']), 'cached': True}
        content = algorithms.generate(kind, chunks, json.loads(row['metadata'])['filename'], options)
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
                    'type': kind, 'scope': scope, 'generator': 'deterministic-v2' if kind == 'QUIZ' else 'deterministic-v1', 'generatorVersion': version,
                    'options': options, 'sourceRevision': revision, 'content': content,
                    'sourceChunkIds': sorted(references), 'createdAt': now, 'updatedAt': now,
                    'analysis': {'sampled': len(chunks) > algorithms.MAX_CHUNKS
                                 or sum(c['text'].count('.') + c['text'].count('?') + c['text'].count('!') for c in chunks) > algorithms.MAX_SENTENCES
                                 or any(len(c['text']) > 12000 for c in chunks),
                                 'chunkLimit': algorithms.MAX_CHUNKS, 'sentenceLimit': algorithms.MAX_SENTENCES}}
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
        row, _, revision = self._source(document_id, user)
        with self.documents.db() as db:
            self._active(db, document_id, user)
            items = db.execute('SELECT payload FROM knowledge_artifacts WHERE document_id=? AND owner=? ORDER BY updated DESC',
                               (document_id, row['owner'])).fetchall()
        artifacts = [json.loads(item['payload']) for item in items]
        # Legacy quizzes remain readable, but their v1 key cannot satisfy v2 requests.
        return {'artifacts': [a for a in artifacts if a['sourceRevision'] == revision and a['generatorVersion'] in
            ((knowledge_quiz.VERSION, '1.0.0') if a['type'] == 'QUIZ' else (algorithms.VERSION,))]}

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
