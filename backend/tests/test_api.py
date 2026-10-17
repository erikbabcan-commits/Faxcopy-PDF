from pathlib import Path
import hashlib
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from app.config import settings, Settings
from app.db import session_factory
from app.manage import provision
from app.models import Job, Tenant, now
from app.schemas import digest
from app.scanning import ScanFailure
from app.storage import job_dir
from app.worker import process_one, validate_result, recover_stale
from conftest import PASSWORD


def test_health_without_login(client):
    assert client.get('/healthz').status_code==200
    assert client.get('/readyz').status_code==200

def test_private_api_requires_session(client):
    assert client.get('/api/jobs').status_code==401
    assert client.get('/api/profiles').status_code==401
    assert client.get('/api/openapi.json').status_code==401

def test_cookie_and_csp(client,account):
    response=client.post('/api/auth/login',headers={'Origin':'http://testserver'},json={'workspace_id':account['tenant'].id,'email':account['user'].email,'password':PASSWORD})
    cookie=response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert "script-src 'self'" in response.headers['content-security-policy']
    assert "unsafe-inline" not in response.headers['content-security-policy']
    assert response.headers['cache-control']=='no-store'

def test_login_wrong_origin(client,account):
    response=client.post('/api/auth/login',headers={'Origin':'http://evil.example'},json={'workspace_id':account['tenant'].id,'email':account['user'].email,'password':PASSWORD})
    assert response.status_code==403

def test_csrf_rejected(client,account):
    assert client.post('/api/auth/logout',headers={'Origin':'http://testserver'}).status_code==403
    assert client.post('/api/auth/logout',headers={**account['headers'],'Origin':'http://evil.example'}).status_code==403

def test_logout_revokes_session(client,account):
    assert client.post('/api/auth/logout',headers=account['headers']).status_code==200
    assert client.get('/api/me').status_code==401

def test_password_change_expires_session_cookie_safely(client,account):
    response=client.post('/api/auth/password',headers=account['headers'],json={'old_password':PASSWORD,'new_password':'Another-Strong-Test-Password-294!'})
    assert response.status_code==200
    cookie=response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert client.get('/api/me').status_code==401

def test_full_upload_scan_report_preview_and_handoff(client,account,upload):
    response=upload();assert response.status_code==201,response.text
    job=response.json()
    assert job['status']=='queued'
    assert process_one() is True
    detail=client.get('/api/jobs/'+job['id']).json()
    assert detail['status']=='review'
    assert detail['report']['release_allowed'] is False
    assert detail['report']['job_id']==job['id']
    assert detail['report']['tenant_id']==account['tenant'].id
    assert detail['report']['profile_id']==job['profile_id']
    assert detail['report']['profile_version']==job['profile_version']
    assert detail['report']['timestamp']
    assert detail['report']['final_state']==detail['status']
    assert detail['report']['engine']['version']
    assert isinstance(detail['report']['findings'],list)
    assert detail['report_digest']==digest(detail['report'])
    assert client.get(f"/api/jobs/{job['id']}/preview").headers['content-type']=='image/png'
    original=client.get(f"/api/jobs/{job['id']}/original")
    assert hashlib.sha256(original.content).hexdigest()==job['sha256']
    assert 'attachment' in original.headers['content-disposition']
    assert client.get(f"/api/jobs/{job['id']}/report").status_code==200
    review=client.post(f"/api/jobs/{job['id']}/review",headers=account['headers'],json={'decision':'accepted','note':'Prevzaté na ďalšie odborné posúdenie.','acknowledge_limits':True})
    assert review.status_code==200,review.text
    assert review.json()['decision']=='accepted'
    assert review.json()['report']['print_ready'] is False
    assert client.post(f"/api/jobs/{job['id']}/review",headers=account['headers'],json={'decision':'accepted','note':'Duplicate decision should fail.','acknowledge_limits':True}).status_code==409
    assert client.get('/api/stats').json()['accepted']==1
    assert any(e['action']=='job.reviewed' for e in client.get('/api/audit').json()['items'])

def test_upload_idempotency_and_mismatch(client,account,upload):
    key=str(uuid.uuid4())
    a=upload(key=key); b=upload(key=key)
    assert a.status_code==201 and b.status_code==200
    assert a.json()['id']==b.json()['id']
    assert upload(key=key,order_ref='different-order').status_code==409
    assert client.get('/api/stats').json()['usage']['uploads']==1

def test_upload_header_is_not_enough(client,account):
    headers={**account['headers'],'Idempotency-Key':str(uuid.uuid4())}
    response=client.post('/api/jobs',headers=headers,files={'file':('fake.pdf',b'not a pdf','application/pdf')},data={'profile_id':account['profile']['id']})
    assert response.status_code==415
    assert client.get('/api/stats').json()['usage']['uploads']==0

def test_quota_enforced(client,account,upload):
    with session_factory()() as db:
        db.execute(update(Tenant).where(Tenant.id==account['tenant'].id).values(monthly_limit=1));db.commit()
    assert upload().status_code==201
    assert upload().status_code==429

def test_cross_tenant_job_and_profile_denied(client,account,upload):
    job=upload().json()
    with session_factory()() as db:
        other,user=provision(db,'Iná tlačiareň','other@example.test',PASSWORD)
    login=client.post('/api/auth/login',headers={'Origin':'http://testserver'},json={'workspace_id':other.id,'email':user.email,'password':PASSWORD})
    headers={'Origin':'http://testserver','X-CSRF-Token':login.json()['csrf_token'],'Idempotency-Key':str(uuid.uuid4())}
    for suffix in ['', '/original','/preview','/report']:
        assert client.get('/api/jobs/'+job['id']+suffix).status_code==404
    assert client.get('/api/jobs').json()['total']==0
    assert client.post('/api/profiles',headers=headers,json={'name':'Forbidden clone','base_profile_id':account['profile']['id'],'rules':account['profile']['rules']}).status_code==404

def test_viewer_cannot_upload_or_change_profile(client,account,upload):
    member=client.post('/api/members',headers=account['headers'],json={'email':'viewer@example.test','password':PASSWORD,'role':'viewer'})
    assert member.status_code==201
    login=client.post('/api/auth/login',headers={'Origin':'http://testserver'},json={'workspace_id':account['tenant'].id,'email':'viewer@example.test','password':PASSWORD})
    headers={'Origin':'http://testserver','X-CSRF-Token':login.json()['csrf_token'],'Idempotency-Key':str(uuid.uuid4())}
    assert client.get('/api/jobs').status_code==200
    assert client.post('/api/profiles',headers=headers,json={'name':'New profile','rules':account['profile']['rules']}).status_code==403
    assert client.get('/api/members').status_code==403
    response=client.post('/api/jobs',headers=headers,files={'file':('a.pdf',b'%PDF-1.7','application/pdf')},data={'profile_id':account['profile']['id']})
    assert response.status_code==403

def test_blocked_job_cannot_be_accepted(client,account,upload):
    job=upload('02-chybajuca-spadavka.pdf').json();process_one()
    body={'decision':'accepted','note':'This must not bypass a known error.','acknowledge_limits':True}
    assert client.post(f"/api/jobs/{job['id']}/review",headers=account['headers'],json=body).status_code==409
    body['decision']='rejected'
    assert client.post(f"/api/jobs/{job['id']}/review",headers=account['headers'],json=body).status_code==200

def test_limits_acknowledgement_required(client,account,upload):
    job=upload().json();process_one()
    assert client.post(f"/api/jobs/{job['id']}/review",headers=account['headers'],json={'decision':'accepted','note':'Review note for test.','acknowledge_limits':False}).status_code==422

def test_invalid_pdf_is_error_and_retry_is_bounded(client,account,upload):
    job=upload('06-poskodeny-subor.pdf').json()
    for i in range(3):
        assert process_one()
        detail=client.get('/api/jobs/'+job['id']).json()
        assert detail['status']=='error'
        response=client.post(f"/api/jobs/{job['id']}/retry",headers=account['headers'])
        assert response.status_code==(200 if i<2 else 409)

def test_new_profile_version_preserves_job_snapshot(client,account,upload):
    job=upload().json()
    new_rules={**account['profile']['rules'],'bleed_mm':5}
    response=client.post('/api/profiles',headers=account['headers'],json={'name':account['profile']['name'],'base_profile_id':account['profile']['id'],'rules':new_rules})
    assert response.status_code==201
    assert response.json()['version']==2
    detail=client.get('/api/jobs/'+job['id']).json()
    assert detail['profile_version']==1
    assert detail['profile_snapshot']['bleed_mm']==3

def test_api_key_scope_and_revocation(client,account,upload):
    result=client.post('/api/keys',headers=account['headers'],json={'name':'Test uploader','scope':'upload','expires_days':1})
    assert result.status_code==201
    key=result.json(); auth={'Authorization':'Bearer '+key['token']}
    assert client.get('/api/profiles',headers=auth).status_code==200
    assert client.get('/api/members',headers=auth).status_code==403
    assert client.get('/api/me',headers=auth).status_code==403
    assert 'token' not in str(client.get('/api/keys').json())
    assert client.delete('/api/keys/'+key['id'],headers=account['headers']).status_code==200
    assert client.get('/api/profiles',headers=auth).status_code==401

def test_readonly_api_key_cannot_upload(client,account):
    result=client.post('/api/keys',headers=account['headers'],json={'name':'Read only','scope':'read','expires_days':1}).json()
    response=client.post('/api/jobs',headers={'Authorization':'Bearer '+result['token'],'Idempotency-Key':str(uuid.uuid4())},files={'file':('a.pdf',b'%PDF-1.7','application/pdf')},data={'profile_id':account['profile']['id']})
    assert response.status_code==403

def test_assistant_fallback_does_not_change_verdict(client,account,upload):
    job=upload('03-nizke-rozlisenie.pdf').json();process_one()
    before=client.get('/api/jobs/'+job['id']).json()
    response=client.post(f"/api/jobs/{job['id']}/assistant",headers=account['headers'])
    assert response.status_code==200
    assert response.json()['mode']=='rules' and response.json()['changes_verdict'] is False
    assert 'rozlíšenie' in response.json()['text']
    after=client.get('/api/jobs/'+job['id']).json()
    assert before['report_digest']==after['report_digest'] and after['decision'] is None

def test_file_delete_releases_storage_not_monthly_count(client,account,upload):
    job=upload().json()
    assert client.delete('/api/jobs/'+job['id'],headers=account['headers']).status_code==200
    assert client.get('/api/jobs/'+job['id']).status_code==404
    assert not job_dir(account['tenant'].id,job['id']).exists()
    usage=client.get('/api/stats').json()['usage']
    assert usage['storage_bytes']==0 and usage['uploads']==1

def test_worker_fails_closed_on_changed_input(client,account,upload):
    job=upload().json();path=job_dir(account['tenant'].id,job['id'])/'original.pdf'
    path.chmod(0o600);path.write_bytes(b'%PDF-1.7\nchanged')
    assert process_one()
    detail=client.get('/api/jobs/'+job['id']).json()
    assert detail['status']=='error' and detail['error_code']=='INPUT_INTEGRITY_FAILED'
    assert detail['report']['job_id']==job['id']
    assert detail['report']['tenant_id']==account['tenant'].id
    assert detail['report']['final_state']=='error'
    assert detail['report']['file_sha256']==job['sha256']

def test_worker_recovery_of_expired_lease(client,account,upload):
    job=upload().json()
    with session_factory()() as db:
        db.execute(update(Job).where(Job.id==job['id']).values(status='processing',lease_token=str(uuid.uuid4()),lease_until=now()-5));db.commit()
    assert recover_stale()==1
    assert client.get('/api/jobs/'+job['id']).json()['error_code']=='WORKER_LEASE_EXPIRED'

def test_scanner_cannot_claim_print_ready(client,account,upload):
    job=upload().json()
    with session_factory()() as db:
        record=db.get(Job,job['id'])
        with pytest.raises(ScanFailure):validate_result(record,{'status':'review','print_ready':True,'release_allowed':True})

def test_origin_and_csrf_required_for_owner_actions(client,account):
    assert client.post('/api/keys',json={'name':'No CSRF','scope':'read','expires_days':1}).status_code==403

def test_invalid_profile_schema_rejected(client,account):
    response=client.post('/api/profiles',headers=account['headers'],json={'name':'Invalid','rules':{'min_pages':10,'max_pages':2}})
    assert response.status_code==422

def test_max_body_size_rejected(client):
    response=client.post('/api/auth/login',content=b'x'*70000,headers={'Content-Type':'application/json','Origin':'http://testserver'})
    assert response.status_code==413

def test_bad_job_filter_rejected(client,account):
    assert client.get('/api/jobs?status=print_ready').status_code==422

@pytest.mark.parametrize('id1,id2',[('../x',str(uuid.uuid4())),(str(uuid.uuid4()),'../x')])
def test_path_traversal_denied(database,id1,id2):
    with pytest.raises(ValueError):job_dir(id1,id2)

def test_production_requires_isolated_scanner_and_https(database):
    with pytest.raises(ValueError):Settings(app_env='production',database_url='sqlite:///x',app_origin='http://x',secure_cookies=False)

def test_rendered_ui_assets_available(client):
    response=client.get('/')
    assert response.status_code==200
    assert 'PressPilot' in response.text and '/assets/main.js' in response.text
    assert client.get('/assets/main.js').status_code==200
    assert client.get('/assets/styles.css').status_code==200
