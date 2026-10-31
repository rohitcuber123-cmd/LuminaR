"""Fresh2M server-enforced security matrix reuses the accepted L contract tests."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
path=ROOT/'tests/institution_v2l/test_writer_security.py'
exec(compile(path.read_text(encoding='utf8'),str(path),'exec'),globals())


def test_writer_rotation_new_principal_and_old_revocation(lab,writer):
    from scripts.institution_v2m_fixture import rotate_writer
    uri=rotate_writer(lab)
    replacement=RestrictedWriter(Configuration(lab.database,uri),'tenant-'+str(uuid4()))
    try:
        replacement.start();assert replacement.pulse() and not writer.pulse()
        lab.db.command('dropUser','fixture_telemetry')
        with pytest.raises(TelemetryError):RestrictedWriter(Configuration(lab.database,lab.telemetry_uri),'tenant-'+str(uuid4()))
        assert replacement.pulse()
        assert record(lab)['current']['instance_id']==replacement.instance_id
    finally:
        replacement.close()
        lab.db.command('createUser','fixture_telemetry',pwd=lab.telemetry_password,roles=[{'role':'fixture_telemetry_writer','db':lab.database}])


def test_reader_rotation_keeps_reader_writer_separate(lab,writer):
    import secrets
    from urllib.parse import quote
    password=secrets.token_urlsafe(32)
    lab.db.command('createUser','fixture_reader_rotated',pwd=password,roles=[{'role':'read','db':lab.database}])
    uri=f'mongodb://fixture_reader_rotated:{quote(password)}@127.0.0.1:{lab.port}/{lab.database}?authSource={lab.database}'
    r=connect_operator(uri,lab.database)
    try:
        assert inspect_telemetry(r,str(uuid4()))['read_only']
        lab.db.command('dropUser','fixture_reader')
        with pytest.raises(DiagnosticError):connect_operator(lab.reader_uri,lab.database)
        with pytest.raises(OperationFailure) as e:r.database[COLLECTION].update_one({'_id':SLOT},{'$set':{'epoch':77}})
        assert e.value.code==13 and writer.pulse()
        with pytest.raises(TelemetryError):RestrictedWriter(Configuration(lab.database,uri),'tenant-'+str(uuid4()))
    finally:
        r.close()
        lab.db.command('createUser','fixture_reader',pwd=lab.read_password,roles=[{'role':'read','db':lab.database}])


def test_dpapi_secret_storage_and_ntfs_acl(lab):
    from scripts.institution_v2m_secrets import protect
    path=lab.root/'protected-test/reader.clixml'
    evidence=protect(lab.root,path,lab.reader_uri)
    assert evidence['encryption']=='Windows SecureString Export-Clixml DPAPI'
    assert evidence['file_protected'] and evidence['directory_protected']
    assert evidence['recovered_matches'] and evidence['plaintext_absent_from_ciphertext']
    assert '(A;;FA;;;SY)' in evidence['file_sddl'] and evidence['current_sid'] in evidence['file_sddl']
    assert ';;;AU)' not in evidence['file_sddl'] and ';;;BU)' not in evidence['file_sddl'] and ';;;WD)' not in evidence['file_sddl']


def test_secret_helper_rejects_outside_fixture_path(lab):
    from scripts.institution_v2m_secrets import command
    outside=lab.root.parent/('must-not-create-'+uuid4().hex+'.clixml')
    payload={'fixture_root':str(lab.root),'secret_path':str(outside),'secret':'never-persist-this-fixture-value'}
    p=subprocess.run(command('protect'),input=json.dumps(payload),capture_output=True,text=True,timeout=15)
    assert p.returncode==3 and not outside.exists()
    assert 'never-persist-this-fixture-value' not in p.stdout+p.stderr


def test_rotation_credential_repr_is_redacted(lab):
    c=Configuration(lab.database,lab.telemetry_uri)
    assert lab.telemetry_uri not in repr(c) and lab.telemetry_password not in repr(c)


def test_production_runtime_preserved_from_m_baseline():
    import hashlib
    baseline=json.loads((ROOT/'reports/institution_v2m_baseline.json').read_text(encoding='utf8'))
    for name in ['search/library_intelligence.py','search/library_intelligence_api.py','backend/services/library_intelligence_store.py',
        'backend/services/library_intelligence_service.py','backend/services/library_worker_observer.py','backend/services/library_worker_telemetry.py',
        'backend/services/library_worker_diagnostics.py','backend/services/library_operator_access.py','scripts/diagnose_worker_telemetry.py']:
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==baseline['source_sha256'][name]


def test_no_frontend_infrastructure_secret_contract():
    names=['LUMINAR_WORKER_TELEMETRY_MONGO_URI','LUMINAR_OPERATOR_MONGO_URI']
    for p in (ROOT/'frontend/src').rglob('*'):
        if p.is_file() and p.suffix in ['.ts','.tsx','.css']:
            text=p.read_text(encoding='utf8')
            assert not any(n in text for n in names)


def test_disabled_restart_retains_native_rows_and_artifacts(lab,worker_factory,library):
    import hashlib
    from backend.services import library_intelligence_store as store
    def until(fn):
        end=time.monotonic()+10
        while not fn():
            assert time.monotonic()<end
            time.sleep(.03)
    first=library();f=configured_factory(lab.database,environ={ENABLE_ENV:'1',URI_ENV:lab.telemetry_uri})
    w=worker_factory(observer_factory=f);w.start();assert w.observer.ready.wait(3)
    until(lambda:(record(lab).get('current') or {}).get('pulse_seq',0)>=1)
    for target in ['SEARCH_INDEX','KNOWLEDGE_GRAPH']:
        j=store.request_build(first,{'sub':'1'},target)
        until(lambda:lab.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})['state']=='SUCCEEDED')
    w.close();w.thread.join(timeout=2)
    rows={n:list(lab.db['institution_intelligence_'+n].find({})) for n in ['jobs','targets','generations']}
    files={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (lab.artifact_root/first).rglob('*') if p.is_file()}
    slot=record(lab)
    v=worker_factory(observer_factory=configured_factory(lab.database,environ={ENABLE_ENV:'0',URI_ENV:lab.telemetry_uri}));v.start()
    assert v.observer is None and record(lab)==slot
    for n,old in rows.items():assert list(lab.db['institution_intelligence_'+n].find({}))==old
    j=store.request_build(library(private=False),{'sub':'1'},'KNOWLEDGE_GRAPH')
    until(lambda:lab.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})['state']=='SUCCEEDED')
    for n,old in rows.items():assert all(lab.db['institution_intelligence_'+n].find_one({'_id':r['_id']})==r for r in old)
    assert all(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in files.items())
    assert record(lab)==slot
