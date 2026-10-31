"""Default-disabled native lifecycle adapter; only trusted in-process hints.

No native store import, job writes, schema provisioning or credential fallback.
Mongo work remains on the single shared2K Agent's own bounded thread.
"""
from dataclasses import dataclass,field
import logging,os,re
from .library_worker_telemetry import Actor,Agent,TelemetryError

LOG=logging.getLogger(__name__)
ENABLE_ENV='LUMINAR_WORKER_TELEMETRY_ENABLED'
URI_ENV='LUMINAR_WORKER_TELEMETRY_MONGO_URI'


@dataclass(frozen=True)
class Configuration:
    database:str
    uri:str=field(repr=False)


class RestrictedWriter(Actor):
    app_name='LuminaR-worker-telemetry'
    def __init__(self,configuration,owner,**kwargs):
        self.configuration=configuration
        super().__init__(configuration.uri,configuration.database,owner,**kwargs)

    def database_allowed(self,database):
        return (isinstance(self.configuration,Configuration) and database==self.configuration.database
                and isinstance(database,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,63}',database) is not None)


class NativeObserver(Agent):
    """One Agent per native instance; these methods never access Mongo."""
    def __init__(self,factory,owner,**kwargs):
        super().__init__(factory,owner,**kwargs);self.report_stopping=True

    def started(self):self.start()
    def claimed(self,job):self.note_claim(job)
    def progress(self,job):self.note_progress(job)
    def finished(self,job):self.note_finished()
    def stopping(self,native_stopped=False):self.close(native_stopped=native_stopped)
    def stopped(self):self.close(native_stopped=True)


def configured_factory(database,*,environ=None):
    """Explicit opt-in only; no .env loader, app URI/JWT/operator fallback or writes."""
    environment=os.environ if environ is None else environ
    if environment.get(ENABLE_ENV)!='1':return None
    uri=environment.get(URI_ENV)
    if not isinstance(uri,str) or not uri:
        LOG.warning('Worker telemetry unavailable: MISSING_WRITER_CREDENTIAL')
        return None
    if not isinstance(database,str) or re.fullmatch(r'[A-Za-z0-9_-]{1,63}',database) is None:
        LOG.warning('Worker telemetry unavailable: INVALID_DATABASE_BINDING')
        return None
    configuration=Configuration(database,uri)
    def factory(owner):return NativeObserver(lambda:RestrictedWriter(configuration,owner),owner)
    return factory
