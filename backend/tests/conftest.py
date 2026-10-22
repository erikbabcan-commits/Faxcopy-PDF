import os
from pathlib import Path
import uuid
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
os.environ['APP_ENV'] = 'test'
os.environ['APP_ORIGIN'] = 'http://testserver'
os.environ['SECURE_COOKIES'] = 'false'
os.environ['STATIC_DIR'] = str(ROOT / 'frontend' / 'dist')
os.environ['SCANNER_URL'] = ''

from app.config import settings
from app.db import engine, session_factory
from app.models import Base
from app.manage import provision

PASSWORD = 'Synthetic-Test-Password-Only-123!'

@pytest.fixture
def database(tmp_path, monkeypatch):
    if engine.cache_info().currsize:
        engine().dispose()
    engine.cache_clear()
    settings.cache_clear()
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "test.db"}')
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    Base.metadata.create_all(engine())
    yield
    engine().dispose()
    engine.cache_clear()
    settings.cache_clear()

@pytest.fixture
def client(database):
    from app.main import app
    with TestClient(app) as client:
        yield client

@pytest.fixture
def account(client):
    with session_factory()() as db:
        tenant, user = provision(db, 'Testová tlačiareň', 'owner@example.test', PASSWORD)
    response = client.post('/api/auth/login', headers={'Origin':'http://testserver'},
        json={'workspace_id':tenant.id,'email':user.email,'password':PASSWORD})
    assert response.status_code == 200, response.text
    headers = {'Origin':'http://testserver','X-CSRF-Token':response.json()['csrf_token']}
    profiles = client.get('/api/profiles').json()
    profile = next(p for p in profiles if p['name'].startswith('Vizitka'))
    return {'tenant':tenant,'user':user,'headers':headers,'profile':profile}

@pytest.fixture
def upload(client, account):
    def put(sample='01-vizitka-kontrola.pdf', key=None, profile=None, filename=None, order_ref='TEST-1001'):
        source = ROOT / 'samples' / sample
        return client.post('/api/jobs', headers={**account['headers'],'Idempotency-Key':key or str(uuid.uuid4())},
            files={'file':(filename or sample,source.read_bytes(),'application/pdf')},
            data={'profile_id':profile or account['profile']['id'],'order_ref':order_ref})
    return put
