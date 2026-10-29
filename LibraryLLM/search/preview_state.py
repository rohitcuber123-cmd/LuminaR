"""Persistence-ready single-row compare-and-swap state. No database on import.

Mongo implementation is injectable and never initializes indexes or seeds data.
The in-memory implementation is a development double, not durable multi-worker IO.
"""
from copy import deepcopy
from threading import Lock
from fastapi import HTTPException


class MemoryStateStore:
    durable=False
    def __init__(self):self.rows={};self.lock=Lock()
    def get(self,key,owner,now):
        with self.lock:
            row=self.rows.get(key)
            if not row or row['owner']!=owner:raise HTTPException(404,'Search state is unavailable.')
            if row['expires_at']<=now:raise HTTPException(410,'Search state expired. Submit the query again.')
            return deepcopy(row)
    def create(self,row):
        with self.lock:
            for key in [k for k,r in self.rows.items() if r['expires_at']<=row['created_at']]:self.rows.pop(key,None)
            if len(self.rows)>=512:raise HTTPException(503,'Search preview is busy. Retry later.')
            if row['_id'] in self.rows:raise HTTPException(409,'Search state changed.')
            self.rows[row['_id']]=deepcopy(row)
    def replace(self,old,new,now):
        with self.lock:
            row=self.rows.get(old['_id'])
            if not row or row['owner']!=old['owner'] or row['version']!=old['version'] or row['expires_at']<=now:
                raise HTTPException(409,'Search state changed or this operation was already used.')
            self.rows[old['_id']]=deepcopy(new)


class MongoStateStore:
    durable=True  # implementation property, NOT evidence of live qualification
    def __init__(self,collection=None,*,collection_factory=None):self._collection=collection;self.factory=collection_factory
    @property
    def collection(self):return self.factory() if self.factory else self._collection
    def get(self,key,owner,now):
        row=self.collection.find_one({'_id':key,'owner':owner})
        if not row:raise HTTPException(404,'Search state is unavailable.')
        if row['expires_at']<=now:raise HTTPException(410,'Search state expired. Submit the query again.')
        return row
    def create(self,row):
        from pymongo.errors import DuplicateKeyError
        try:self.collection.insert_one(deepcopy(row))
        except DuplicateKeyError as error:raise HTTPException(409,'Search state changed.') from error
    def replace(self,old,new,now):
        # One atomic row replacement consumes all operation IDs from the old
        # version and publishes the next accepted plan/IR/source together.
        result=self.collection.replace_one({'_id':old['_id'],'owner':old['owner'],'version':old['version'],
            'parser_version':old['parser_version'],'source_digest':old['source_digest'],'ir_digest':old['ir_digest'],
            'expires_at':{'$gt':now}},deepcopy(new))
        if result.modified_count!=1:raise HTTPException(409,'Search state changed or this operation was already used.')
