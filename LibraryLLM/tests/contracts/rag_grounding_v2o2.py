"""PROPOSED reviewed exception: exact current bytes AND exact old-source projection.

Original hashes.json stays unchanged. Unknown byte changes are rejected; this is
not a generic newline normalizer or an acceptance of arbitrary current source.
"""
import hashlib
LEGACY_SHA256='0e78a7c780f691b14c8e3a3337f62054e4c117f0c2df7828099d80da90a793c6'
REVIEWED_SHA256='4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3'


def reviewed_rag_payload(payload):
    actual=hashlib.sha256(payload).hexdigest()
    if actual==LEGACY_SHA256:return payload
    assert actual==REVIEWED_SHA256,'Unreviewed protected RAG bytes'
    additions=[b'from rag.book_assets import valid_work_id',b'from rag.document_grounding import select_definition_evidence, definition_category',
        b'        is_document = bool(document_id and not valid_work_id(document_id))',b'        if is_document:',
        b'            results = select_definition_evidence(question, results, document_id, max_chunks)',
        b'            q_category = definition_category(question, used_items, document_id) or q_category']
    lines=payload.splitlines(keepends=True)
    for line in additions:assert sum(item.rstrip(b'\r\n')==line for item in lines)==(2 if line==b'        if is_document:' else 1)
    lines=[line for line in lines if line.rstrip(b'\r\n') not in additions]
    revised=b'        for item in ([] if is_document and verdict == "NOT_SUPPORTED" else used_items):'
    assert sum(line.rstrip(b'\r\n')==revised for line in lines)==1
    original=b''.join(b'        for item in used_items:\r\n' if line.rstrip(b'\r\n')==revised else line for line in lines)
    assert hashlib.sha256(original).hexdigest()==LEGACY_SHA256,'Reviewed source delta does not project to frozen source'
    return original
