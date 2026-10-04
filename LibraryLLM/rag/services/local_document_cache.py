"""Bounded portable prepared documents; authenticated ciphertext only on clients."""
import base64
import hashlib
import hmac
import io
import json
import os
import struct
import time
import zipfile
from uuid import uuid4

import numpy as np
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import HTTPException

FORMAT = 1
DIMENSION = 384
MAX_BYTES = int(os.getenv('KNOW_MORE_CACHE_MAX_BUNDLE_BYTES', str(64 * 1024 * 1024)))
MAX_PLAIN = 128 * 1024 * 1024
MAX_CHUNKS = 20000
FILES = {'manifest.json', 'chunks.json', 'embeddings.npy', 'source_map.json'}
MAGIC = b'LUMKMC1\0'


def fail(code='INVALID_LOCAL_CACHE'):
    message = ('This cached document was created with an older processing version. Re-upload the document to prepare it again.'
               if code == 'CACHE_INCOMPATIBLE' else 'This device copy could not be verified. Re-upload the original PDF.')
    raise HTTPException(409 if code == 'CACHE_INCOMPATIBLE' else 400, {'code': code, 'message': message})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def fingerprint():
    import inspect
    from rag.services.document_service import clean_text, chunk_text, DocumentService, MODEL_NAME, CHUNK_SIZE, CHUNK_OVERLAP
    config = {'format': FORMAT, 'model': MODEL_NAME, 'dimension': DIMENSION, 'dtype': 'float32',
              'normalized': True, 'chunk_size': CHUNK_SIZE, 'overlap': CHUNK_OVERLAP, 'source_map': 1,
              'processing': hashlib.sha256(''.join(inspect.getsource(f) for f in
                  (clean_text, chunk_text, DocumentService.extract_pdf, DocumentService.create_chunks, DocumentService.embed_chunks)).encode()).hexdigest()}
    return hashlib.sha256(canonical(config)).hexdigest()


class LocalDocumentCache:
    def __init__(self, master=None, enabled=None):
        self.enabled = os.getenv('KNOW_MORE_DEVICE_CACHE_ENABLED', 'false').lower() == 'true' if enabled is None else enabled
        self.version = int(os.getenv('KNOW_MORE_CACHE_KEY_VERSION', '1'))
        if master is None:
            try:
                master = base64.b64decode(os.getenv('KNOW_MORE_CACHE_MASTER_KEY', ''), validate=True)
            except ValueError:
                master = b''
        self.master = master
        if self.enabled and len(master) != 32:
            raise RuntimeError('Device cache requires a configured 32-byte KNOW_MORE_CACHE_MASTER_KEY (base64).')
        self.metrics = {'exports': 0, 'restores': 0, 'failures': 0, 'encrypted_bytes': 0, 'failures_by_code': {}, 'pipeline_incompatibilities': 0, 'average_encrypted_bytes': 0.0}

    def record_failure(self, error):
        code = error.detail.get('code', 'HTTP_ERROR') if isinstance(error.detail, dict) else 'HTTP_ERROR'
        self.metrics['failures'] += 1
        failures = self.metrics['failures_by_code']
        failures[code] = failures.get(code, 0) + 1
        if code == 'CACHE_INCOMPATIBLE':
            self.metrics['pipeline_incompatibilities'] += 1

    def require_enabled(self):
        if not self.enabled:
            raise HTTPException(503, {'code': 'CACHE_DISABLED', 'message': 'Device caching is not enabled.'})

    def scope(self, owner):
        self.require_enabled()
        return hmac.new(self.master, b'luminar:owner-scope:v1:' + str(owner).encode(), hashlib.sha256).hexdigest()

    def key(self, owner, purpose):
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=b'luminar-know-more-v1',
                    info=f'luminar:cache:{purpose}:{owner}:key-{self.version}'.encode()).derive(self.master)

    def encrypt(self, owner, payload, purpose, cache_id):
        header = canonical({'format_version': FORMAT, 'key_version': self.version, 'owner_scope_id': self.scope(owner),
                            'pipeline_fingerprint': fingerprint(), 'cache_id': cache_id, 'purpose': purpose})
        nonce = os.urandom(12)
        ciphertext = AESGCM(self.key(owner, purpose)).encrypt(nonce, payload, header)
        return MAGIC + struct.pack('>I', len(header)) + header + nonce + ciphertext

    def decrypt(self, owner, blob, purpose):
        self.require_enabled()
        try:
            if len(blob) > MAX_BYTES or len(blob) < 44 or blob[:8] != MAGIC:
                fail()
            size = struct.unpack('>I', blob[8:12])[0]
            if size > 2048 or size < 1 or len(blob) < 12 + size + 28:
                fail()
            aad = blob[12:12+size]
            header = json.loads(aad)
            if set(header) != {'format_version', 'key_version', 'owner_scope_id', 'pipeline_fingerprint', 'cache_id', 'purpose'}:
                fail()
            if header['key_version'] != self.version or header['format_version'] != FORMAT:
                fail('CACHE_INCOMPATIBLE')
            if header['purpose'] != purpose or not hmac.compare_digest(str(header['owner_scope_id']), self.scope(owner)):
                fail()
            if not isinstance(header['cache_id'], str) or len(header['cache_id']) != 32:
                fail()
            int(header['cache_id'], 16)
            data = AESGCM(self.key(owner, purpose)).decrypt(blob[12+size:24+size], blob[24+size:], aad)
            if header['pipeline_fingerprint'] != fingerprint():
                fail('CACHE_INCOMPATIBLE')
            return header, data
        except HTTPException:
            raise
        except Exception:
            fail()

    def pack(self, document, chunks, vectors, cache_id):
        vector_file = io.BytesIO()
        np.save(vector_file, vectors, allow_pickle=False)
        portable = [{k: c[k] for k in ('chunk_id', 'page', 'text')} for c in chunks]
        source_map = [{'chunk_id': c['chunk_id'], 'page': c['page']} for c in portable]
        entries = {'chunks.json': canonical(portable), 'embeddings.npy': vector_file.getvalue(), 'source_map.json': canonical(source_map)}
        manifest = {'format_version': FORMAT, 'cache_id': cache_id, 'document_sha256': document['document_sha256'],
                    'pipeline_fingerprint': fingerprint(), 'chunker_version': 'page-character-3000-overlap400-v1',
                    'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2', 'embedding_dimension': DIMENSION,
                    'embedding_dtype': 'float32', 'embedding_normalized': True, 'chunk_count': len(chunks),
                    'source_map_version': 1, 'created_at': time.time(), 'filename': document['filename'], 'pages': document['pages'],
                    'checksums': {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()}}
        entries['manifest.json'] = canonical(manifest)
        if sum(map(len, entries.values())) > MAX_PLAIN:
            raise HTTPException(413, 'Prepared document exceeds the device cache limit.')
        output = io.BytesIO()
        # Stored entries bound allocation and eliminate decompression amplification.
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        if output.tell() > MAX_BYTES - 4096:
            raise HTTPException(413, 'Prepared document exceeds the device cache limit.')
        return output.getvalue()

    def unpack(self, payload, cache_id):
        try:
            if len(payload) > MAX_BYTES:
                fail()
            # Bound the central directory before ZipFile allocates ZipInfo objects.
            if len(payload) < 22 or payload[-22:-18] != b'PK\x05\x06':
                fail()
            disk, central_disk, disk_entries, entry_count, central_size, central_offset, comment = struct.unpack('<4H2IH', payload[-18:])
            if (disk or central_disk or disk_entries != 4 or entry_count != 4 or comment
                    or central_size > 1024 or central_offset + central_size != len(payload) - 22):
                fail()
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                entries = archive.infolist()
                if len(entries) != 4 or {e.filename for e in entries} != FILES:
                    fail()
                if any(e.flag_bits & 1 or e.compress_type != zipfile.ZIP_STORED or e.file_size > MAX_PLAIN
                       or e.file_size / max(1, e.compress_size) > 100 for e in entries):
                    fail()
                if sum(e.file_size for e in entries) > MAX_PLAIN:
                    fail()
                contents = {e.filename: archive.read(e) for e in entries}
            manifest = json.loads(contents['manifest.json'])
            expected = {'format_version', 'cache_id', 'document_sha256', 'pipeline_fingerprint', 'chunker_version',
                        'embedding_model', 'embedding_dimension', 'embedding_dtype', 'embedding_normalized', 'chunk_count',
                        'source_map_version', 'created_at', 'filename', 'pages', 'checksums'}
            if set(manifest) != expected or manifest['cache_id'] != cache_id:
                fail()
            if manifest['format_version'] != FORMAT or manifest['pipeline_fingerprint'] != fingerprint():
                fail('CACHE_INCOMPATIBLE')
            if (manifest['embedding_dimension'] != DIMENSION or manifest['embedding_dtype'] != 'float32'
                    or manifest['embedding_normalized'] is not True or manifest['source_map_version'] != 1
                    or manifest['embedding_model'] != 'sentence-transformers/all-MiniLM-L6-v2'
                    or manifest['chunker_version'] != 'page-character-3000-overlap400-v1'):
                fail('CACHE_INCOMPATIBLE')
            if (type(manifest['chunk_count']) is not int or not 0 < manifest['chunk_count'] <= MAX_CHUNKS
                    or type(manifest['pages']) is not int or not 0 < manifest['pages'] <= 10000
                    or not isinstance(manifest['filename'], str) or not 0 < len(manifest['filename']) <= 255
                    or len(manifest['document_sha256']) != 64):
                fail()
            int(manifest['document_sha256'], 16)
            if set(manifest['checksums']) != FILES - {'manifest.json'}:
                fail()
            for name, checksum in manifest['checksums'].items():
                if not hmac.compare_digest(hashlib.sha256(contents[name]).hexdigest(), checksum):
                    fail()
            chunks = json.loads(contents['chunks.json'])
            if not isinstance(chunks, list) or len(chunks) != manifest['chunk_count']:
                fail()
            if any(set(c) != {'chunk_id', 'page', 'text'} or not isinstance(c['text'], str) or not 0 < len(c['text']) <= 3000
                   or type(c['page']) is not int or not 1 <= c['page'] <= manifest['pages']
                   or not isinstance(c['chunk_id'], str) or len(c['chunk_id']) > 100 for c in chunks):
                fail()
            if len({c['chunk_id'] for c in chunks}) != len(chunks):
                fail()
            if json.loads(contents['source_map.json']) != [{'chunk_id': c['chunk_id'], 'page': c['page']} for c in chunks]:
                fail()
            stream = io.BytesIO(contents['embeddings.npy'])
            version = np.lib.format.read_magic(stream)
            if version != (1, 0):
                fail()
            shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream)
            if shape != (len(chunks), DIMENSION) or fortran or dtype != np.dtype('float32') or dtype.hasobject:
                fail()
            if len(contents['embeddings.npy']) != stream.tell() + len(chunks) * DIMENSION * 4:
                fail()
            vectors = np.load(io.BytesIO(contents['embeddings.npy']), allow_pickle=False)
            if not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=2e-3):
                fail()
            return manifest, chunks, vectors
        except HTTPException:
            raise
        except Exception:
            fail()

    def export(self, owner, document, chunks, vectors):
        self.require_enabled()
        cache_id = document.get('cache_id') or uuid4().hex
        bundle = self.pack(document, chunks, vectors, cache_id)
        blob = self.encrypt(owner, bundle, 'bundle', cache_id)
        descriptor = {k: document[k] for k in ('filename', 'pages', 'document_sha256')}
        descriptor.update(cache_id=cache_id, pipeline_fingerprint=fingerprint(), created_at=time.time())
        encrypted_descriptor = base64.b64encode(self.encrypt(owner, canonical(descriptor), 'descriptor', cache_id)).decode()
        self.metrics['exports'] += 1
        self.metrics['encrypted_bytes'] += len(blob)
        self.metrics['average_encrypted_bytes'] = self.metrics['encrypted_bytes'] / self.metrics['exports']
        return blob, {'cache_id': cache_id, 'owner_scope_id': self.scope(owner), 'encrypted_descriptor': encrypted_descriptor,
                      'format_version': FORMAT, 'blob_size': len(blob)}

    def inspect(self, owner, descriptor):
        if len(descriptor) > 8192:
            fail()
        try:
            header, data = self.decrypt(owner, base64.b64decode(descriptor, validate=True), 'descriptor')
            result = json.loads(data)
            if result['cache_id'] != header['cache_id']:
                fail()
            return result
        except HTTPException:
            raise
        except Exception:
            fail()
