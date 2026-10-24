"""Synthetic regressions for route authorization and pre-auth parser boundaries."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.mark.parametrize("scope", ["read", "upload"])
@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/members", None),
    ("POST", "/api/members", {"email":"inert@example.test","password":"Synthetic-only-password-123!","role":"owner"}),
    ("POST", "/api/keys", {"name":"Unauthorized synthetic mint","scope":"upload"}),
])
def test_host_cannot_expand_key_scope(client, account, scope, method, path, body):
    response=client.post('/api/keys',headers=account['headers'],json={'name':'Boundary regression','scope':scope})
    token=response.json()['token']
    for host in ('testserver','testserver/api/jobs?','testserver/api/jobs#'):
        r=client.request(method,path,headers={'Authorization':'Bearer '+token,'Host':host},json=body)
        assert r.status_code in (400,403)

@pytest.mark.parametrize('path',['/api/jobs','/scan'])
def test_urlencoded_body_never_reaches_parser(client, monkeypatch, path):
    from starlette.formparsers import FormParser
    async def forbidden_parse(self):
        pytest.fail('urlencoded parser must not run on file endpoints')
    monkeypatch.setattr(FormParser,'parse',forbidden_parse)
    if path=='/scan':
        from app.scanner_service import app as scanner_app
        with TestClient(scanner_app) as scanner:
            response=scanner.post(path,content=b'a=1&'*6000,headers={'Content-Type':'application/x-www-form-urlencoded'})
    else:
        response=client.post(path,content=b'a=1&'*6000,headers={'Content-Type':'application/x-www-form-urlencoded'})
    assert response.status_code==415

@pytest.mark.parametrize('host',['localhost','localhost:8080','127.0.0.1:8080','[::1]:8080','example.test:443'])
def test_valid_host_syntax_remains_usable(client,host):
    assert client.get('/healthz',headers={'Host':host}).status_code==200

@pytest.mark.parametrize('host',['testserver/path','testserver?x','testserver#x','user@testserver','testserver\\path'])
def test_invalid_host_syntax_rejected(client,host):
    assert client.get('/healthz',headers={'Host':host}).status_code==400
