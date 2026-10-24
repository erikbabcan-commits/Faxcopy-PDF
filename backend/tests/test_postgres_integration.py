"""Run only against the explicitly supplied disposable PostgreSQL test instance."""
import os
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, select, update
from sqlalchemy.exc import DBAPIError
from app.config import settings
from app.db import engine, session_factory
from app.models import Job, User, now
from app.manage import migrate, provision
from app.worker import claim_job, process_one, recover_stale

pytestmark = pytest.mark.skipif(not os.getenv('PP_TEST_RUNTIME_URL'), reason='Disposable PostgreSQL URLs not supplied')

@pytest.fixture
def pg(monkeypatch,tmp_path):
    if engine.cache_info().currsize:engine().dispose()
    engine.cache_clear();settings.cache_clear()
    monkeypatch.setenv('DATABASE_URL',os.environ['PP_TEST_MIGRATION_URL'])
    migrate()
    engine().dispose();engine.cache_clear();settings.cache_clear()
    admin=create_engine(os.environ['PP_TEST_ADMIN_URL'])
    with admin.begin() as c:
        c.execute(text('TRUNCATE tenants, login_buckets, worker_heartbeats CASCADE'))
    monkeypatch.setenv('DATABASE_URL',os.environ['PP_TEST_RUNTIME_URL'])
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'data'))
    from app.main import app
    with TestClient(app) as client:
        with session_factory()() as db:
            tenant,user=provision(db,'Synthetic PG workspace','pg@example.test','Synthetic-Only-Password-123!')
        r=client.post('/api/auth/login',headers={'Origin':'http://testserver'},json={'workspace_id':tenant.id,'email':user.email,'password':'Synthetic-Only-Password-123!'})
        assert r.status_code==200
        headers={'Origin':'http://testserver','X-CSRF-Token':r.json()['csrf_token']}
        profile=next(p for p in client.get('/api/profiles').json() if p['name'].startswith('Vizitka'))
        yield client,tenant,user,headers,profile
    engine().dispose();engine.cache_clear();settings.cache_clear();admin.dispose()

def upload(pg,key):
    from conftest import ROOT
    client,tenant,user,headers,profile=pg
    return client.post('/api/jobs',headers={**headers,'Idempotency-Key':key},data={'profile_id':profile['id']},
        files={'file':('synthetic.pdf',(ROOT/'samples/01-vizitka-kontrola.pdf').read_bytes(),'application/pdf')})

def test_runtime_has_dml_but_no_admin_or_schema_privileges(pg):
    with engine().connect() as c:
        row=c.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user')).one()
        assert row==(False,False,False)
        assert c.execute(text("SELECT has_schema_privilege(current_user,'public','CREATE')")).scalar() is False
    with engine().begin() as c,pytest.raises(DBAPIError):c.execute(text('CREATE TABLE forbidden_ddl (id integer)'))
    with engine().begin() as c,pytest.raises(DBAPIError):c.execute(text('ALTER TABLE jobs ADD COLUMN forbidden integer'))
    with engine().begin() as c,pytest.raises(DBAPIError):c.execute(text('SELECT * FROM pg_authid'))

def test_postgres_full_flow_and_idempotent_upload(pg):
    a=upload(pg,'synthetic-pg-idempotency');b=upload(pg,'synthetic-pg-idempotency')
    assert a.status_code==201 and b.status_code==200 and a.json()['id']==b.json()['id']
    assert process_one()
    r=pg[0].get('/api/jobs/'+a.json()['id'])
    assert r.json()['status']=='review' and r.json()['preview_available']
    r=pg[0].post('/api/jobs/'+a.json()['id']+'/review',headers=pg[3],json={'decision':'accepted','note':'Synthetic manual handoff only','acknowledge_limits':True})
    assert r.status_code==200 and r.json()['report']['release_allowed'] is False

def test_two_workers_claim_distinct_jobs(pg):
    for key in ['synthetic-pg-claim-one','synthetic-pg-claim-two']:assert upload(pg,key).status_code==201
    gate=threading.Barrier(2)
    def claim():gate.wait();return claim_job()
    with ThreadPoolExecutor(2) as pool:jobs=list(pool.map(lambda _:claim(),range(2)))
    assert all(jobs) and jobs[0].id!=jobs[1].id
    assert all(j.attempts==1 and j.status=='processing' for j in jobs)

def test_stale_worker_cannot_publish_after_lease_recovery(pg,monkeypatch):
    import app.worker as worker
    from app.inspector import inspect_pdf
    job=upload(pg,'synthetic-pg-stale-worker').json()
    def stale_scan(path,rules):
        with session_factory()() as db:
            db.execute(update(Job).where(Job.id==job['id']).values(lease_until=now()-1));db.commit()
        assert recover_stale()==1
        return {'report':inspect_pdf(path.read_bytes(),rules),'preview_base64':None}
    monkeypatch.setattr(worker,'scan',stale_scan)
    assert process_one()
    detail=pg[0].get('/api/jobs/'+job['id']).json()
    assert detail['status']=='error' and detail['error_code']=='WORKER_LEASE_EXPIRED'
    assert detail['report'] is None

def test_concurrent_reviews_have_one_winner(pg):
    job=upload(pg,'synthetic-pg-review-race').json();assert process_one()
    client=pg[0];cookies=dict(client.cookies);barrier=threading.Barrier(2)
    def review(_):
        from app.main import app
        with TestClient(app) as c:
            c.cookies.update(cookies);barrier.wait()
            return c.post('/api/jobs/'+job['id']+'/review',headers=pg[3],json={'decision':'accepted','note':'Synthetic simultaneous review','acknowledge_limits':True}).status_code
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(review,range(2)))
    assert sorted(results)==[200,409]

def test_postgres_cross_tenant_read_and_mutation_denied(pg):
    job=upload(pg,'synthetic-pg-tenant-isolation').json()
    with session_factory()() as db:tenant,user=provision(db,'Other synthetic workspace','other-pg@example.test','Synthetic-Only-Password-123!')
    client=pg[0]
    r=client.post('/api/auth/login',headers={'Origin':'http://testserver'},json={'workspace_id':tenant.id,'email':user.email,'password':'Synthetic-Only-Password-123!'})
    headers={'Origin':'http://testserver','X-CSRF-Token':r.json()['csrf_token']}
    for suffix in ['', '/original', '/preview', '/report']:assert client.get('/api/jobs/'+job['id']+suffix).status_code==404
    assert client.post('/api/jobs/'+job['id']+'/retry',headers=headers).status_code==404
    assert client.delete('/api/jobs/'+job['id'],headers=headers).status_code==404


def test_concurrent_upload_reserves_quota_once(pg):
    from app.main import app
    from app.models import Tenant
    cookies=dict(pg[0].cookies);barrier=threading.Barrier(2)
    def put(_):
        with TestClient(app) as client:
            client.cookies.update(cookies);barrier.wait()
            return upload((client,*pg[1:]),'synthetic-pg-concurrent-upload').status_code
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(put,range(2)))
    assert 201 in results and all(code in (200,201,409) for code in results)
    with session_factory()() as db:
        assert len(db.scalars(select(Job)).all())==1
        assert db.get(Tenant,pg[1].id).monthly_uploads==1


def test_remote_scanner_protocol_with_postgres(pg,monkeypatch):
    import secrets,socket,subprocess,sys,time
    import httpx
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    token=secrets.token_urlsafe(40)
    environment={'PATH':os.environ['PATH'],'SCANNER_TOKEN':token,'PYTHONDONTWRITEBYTECODE':'1'}
    server=subprocess.Popen([sys.executable,'-m','uvicorn','app.scanner_service:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(trust_env=False) as c:
            for _ in range(100):
                try:
                    if c.get(f'http://127.0.0.1:{port}/healthz').status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.05)
            else:raise AssertionError('Synthetic scanner did not start')
        monkeypatch.setenv('SCANNER_URL',f'http://127.0.0.1:{port}')
        monkeypatch.setenv('SCANNER_TOKEN',token);settings.cache_clear()
        job=upload(pg,'synthetic-pg-remote-scanner').json()
        assert process_one()
        detail=pg[0].get('/api/jobs/'+job['id']).json()
        assert detail['status']=='review' and detail['preview_available']
        assert detail['report']['release_allowed'] is False
    finally:
        server.terminate();server.wait(timeout=5)
