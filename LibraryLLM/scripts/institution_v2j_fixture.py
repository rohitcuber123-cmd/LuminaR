"""Task-owned auth-enabled Mongo fixture, never the existing Mongo service."""
from pathlib import Path
import gc,json,os,secrets,socket,subprocess,tempfile,time
from urllib.parse import quote
from uuid import uuid4
from pymongo import MongoClient


class AuthMongo:
    def __enter__(self):
        candidates=sorted(Path('C:/Program Files/MongoDB/Server').glob('*/bin/mongod.exe'),reverse=True)
        if not candidates:raise RuntimeError('Auth-enabled mongod fixture is not available')
        self.temp=tempfile.TemporaryDirectory(prefix='luminar-v2j-auth-')
        self.root=Path(self.temp.name)
        (self.root/'db').mkdir()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
        self.process=subprocess.Popen([str(candidates[0]),'--dbpath',str(self.root/'db'),'--bind_ip','127.0.0.1',
            '--port',str(self.port),'--auth','--logpath',str(self.root/'mongo.log'),'--quiet'],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.password=secrets.token_urlsafe(32)
        self.database='luminar_v2j_test_'+uuid4().hex[:16]
        self.read_password=secrets.token_urlsafe(32)
        anonymous=MongoClient(f'mongodb://127.0.0.1:{self.port}',serverSelectionTimeoutMS=200)
        deadline=time.monotonic()+20
        try:
            while True:
                try:anonymous.admin.command('ping');break
                except Exception:
                    if time.monotonic()>deadline:raise RuntimeError('Fixture server did not start') from None
                    time.sleep(.1)
            anonymous.admin.command('createUser','fixture_admin',pwd=self.password,roles=[{'role':'root','db':'admin'}])
        finally:anonymous.close()
        self.writer_uri=f'mongodb://fixture_admin:{quote(self.password)}@127.0.0.1:{self.port}/{self.database}?authSource=admin'
        self.writer=MongoClient(self.writer_uri,serverSelectionTimeoutMS=2000)
        self.db=self.writer[self.database]
        self.db.command('createUser','fixture_reader',pwd=self.read_password,roles=[{'role':'read','db':self.database}])
        self.reader_uri=f'mongodb://fixture_reader:{quote(self.read_password)}@127.0.0.1:{self.port}/{self.database}?authSource={self.database}'
        self.artifact_root=self.root/'tenant-artifacts'
        self.artifact_root.mkdir()
        return self

    def __exit__(self,*exc):
        try:
            self.writer.admin.command('shutdown',force=True)
        except Exception:pass
        self.writer.close()
        try:self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate();self.process.wait(timeout=5)
        gc.collect()
        self.temp.cleanup()


def seed_database(fixture):
    """Only the disposable writer seeds collections/indexes. CLI never does."""
    for name,keys,kwargs in [
        ('jobs','job_id',{'unique':True}),('jobs',[('state',1),('created_at',1)],{}),
        ('jobs',[('library_id',1),('target',1)],{'unique':True,'partialFilterExpression':{'effective_active':True}}),
        ('targets',[('library_id',1),('target',1)],{'unique':True}),
        ('generations','generation_id',{'unique':True})]:
        fixture.db['institution_intelligence_'+name if name!='generations' else 'institution_intelligence_generations'].create_index(keys,**kwargs)
