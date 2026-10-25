"""Disposable CI recovery proof. Never use this as a production restore command."""
import argparse
import io
import json
import os
from pathlib import PurePosixPath
import re
import subprocess
import tarfile
from compose_smoke import PROJECT, PROBE

DATABASE = "presspilot_recovery_ci"
MAX_BACKUP_BYTES = 64 * 1024**2


def run(args, data=None, required=True):
    result = subprocess.run(args, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if required and result.returncode:
        # Do not echo subprocess output: it can contain a synthetic session or backup bytes.
        raise RuntimeError(f"Recovery command failed (exit {result.returncode}): {args[0]}")
    return result


def archive_members(data):
    if len(data) > MAX_BACKUP_BYTES:
        raise ValueError("Synthetic document archive exceeds limit")
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        seen = set()
        size = 0
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "documents":
                raise ValueError("Unsafe document archive path")
            if str(path) in seen or not (member.isdir() or member.isfile()):
                raise ValueError("Duplicate or non-regular archive member")
            seen.add(str(path))
            size += member.size
            if size > MAX_BACKUP_BYTES:
                raise ValueError("Expanded document archive exceeds limit")
        return len(seen)


EXTRACT = r'''
import io,os,sys,tarfile
from pathlib import Path,PurePosixPath
os.umask(0o077)
root=Path('/tmp/presspilot-recovery-check')
root.mkdir()  # Fail if a destination already exists; never overwrite it.
raw=sys.stdin.buffer.read(64*1024**2+1)
assert len(raw)<=64*1024**2
seen=set();size=0
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
    for member in archive:
        name=PurePosixPath(member.name)
        assert not name.is_absolute() and '..' not in name.parts and name.parts[0]=='documents'
        assert str(name) not in seen and (member.isdir() or member.isfile())
        seen.add(str(name));size+=member.size;assert size<=64*1024**2
        path=root.joinpath(*name.parts)
        if member.isdir():path.mkdir(parents=True,exist_ok=True)
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as output:output.write(archive.extractfile(member).read())
            path.chmod(0o440 if path.name=='original.pdf' else 0o600)
'''

VALIDATE = r'''
import hashlib,json,os,secrets,sys
from sqlalchemy.engine import make_url
ctx=json.load(sys.stdin)
url=make_url(os.environ['DATABASE_URL'])
assert url.database=='presspilot' and os.environ.get('APP_ENV','pilot')=='pilot'
os.environ['DATABASE_URL']=url.set(database='presspilot_recovery_ci').render_as_string(hide_password=False)
os.environ['DATA_DIR']='/tmp/presspilot-recovery-check'
from fastapi.testclient import TestClient
from app.main import app
from app.db import session_factory,engine
from app.manage import provision
from app.reconciliation import reconcile_storage
from sqlalchemy import text
with TestClient(app) as client:
    headers={'Cookie':ctx['cookie']}
    me=client.get('/api/me',headers=headers);assert me.status_code==200
    assert me.json()['workspace']['id']==ctx['tenant_id']
    job=client.get('/api/jobs/'+ctx['job_id'],headers=headers).json()
    assert job['decision']=='accepted' and job['report_digest']==ctx['report_digest']
    assert job['report']['release_allowed'] is False
    original=client.get('/api/jobs/'+ctx['job_id']+'/original',headers=headers)
    preview=client.get('/api/jobs/'+ctx['job_id']+'/preview',headers=headers)
    assert original.status_code==preview.status_code==200
    assert hashlib.sha256(original.content).hexdigest()==ctx['original_sha256']
    assert hashlib.sha256(preview.content).hexdigest()==ctx['preview_sha256']
    assert client.get('/api/stats',headers=headers).json()['usage']['storage_bytes']==len(original.content)+len(preview.content)
    report=reconcile_storage()
    assert not report['missing'] and not report['size_mismatches'] and not report['untracked']
    assert all(t['difference_bytes']==0 for t in report['tenants'])
    with engine().connect() as connection:
        assert connection.execute(text('SELECT rolsuper FROM pg_roles WHERE rolname=current_user')).scalar() is False
        assert connection.execute(text("SELECT has_schema_privilege(current_user,'public','CREATE')")).scalar() is False
    password=secrets.token_urlsafe(32)
    with session_factory()() as db:tenant,user=provision(db,'Other synthetic restored tenant','other-restored@example.test',password)
    login=client.post('/api/auth/login',headers={'Origin':'http://localhost:8080'},json={'workspace_id':tenant.id,'email':user.email,'password':password})
    assert login.status_code==200
    assert client.get('/api/jobs/'+ctx['job_id']).status_code==404
print(json.dumps({'status':'passed','restored_session':True,'tenant_isolation':True,'original_hash':True,'preview_hash':True,'report_and_decision':True,'storage_accounting':True,'runtime_not_admin':True}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', choices=[PROJECT], required=True)
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REPOSITORY') != 'erikbabcan-commits/Faxcopy-PDF':
        raise SystemExit('This probe is restricted to the disposable repository CI runner')
    compose = ['docker', 'compose', '-p', args.project]
    seed = "import os\nassert os.environ.get('APP_ENV','pilot')=='pilot'\n" + PROBE + r'''
status,data,_=request('GET','/api/jobs/'+job['id']);assert status==200
print(json.dumps({'cookie':cookie,'tenant_id':tenant.id,'job_id':job['id'],
    'report_digest':json.loads(data)['report_digest'],'original_sha256':hashlib.sha256(pdf).hexdigest(),
    'preview_sha256':hashlib.sha256(preview).hexdigest()}))
'''
    fixture = json.loads(run(compose + ['exec', '-T', 'api', 'python', '-'], seed.encode()).stdout.splitlines()[-1])
    api_id = run(compose + ['ps', '-q', 'api']).stdout.decode().strip()
    if not re.fullmatch(r'[0-9a-f]{12,64}', api_id):
        raise ValueError('Invalid synthetic API container ID')
    try:
        run(compose + ['pause', 'api', 'worker'])
        dump = run(compose + ['exec', '-T', 'db', 'pg_dump', '-U', 'presspilot_admin', '-Fc', 'presspilot']).stdout
        documents = run(['docker', 'cp', api_id + ':/app/data/documents', '-']).stdout
    finally:
        run(compose + ['unpause', 'api', 'worker'], required=False)
    if len(dump) > MAX_BACKUP_BYTES:
        raise ValueError('Synthetic database archive exceeds limit')
    members = archive_members(documents)
    invalid = run(compose + ['exec', '-T', 'db', 'pg_restore', '--list'], dump[:32], required=False)
    if invalid.returncode == 0:
        raise AssertionError('Truncated database backup unexpectedly accepted')
    # createdb fails if the target already exists. Never drop or overwrite an existing DB.
    run(compose + ['exec', '-T', 'db', 'createdb', '-U', 'presspilot_admin', '-O', 'presspilot_migrator', DATABASE])
    sql = f'REVOKE ALL ON DATABASE {DATABASE} FROM PUBLIC; GRANT CONNECT ON DATABASE {DATABASE} TO presspilot_runtime, presspilot_migrator;'
    run(compose + ['exec', '-T', 'db', 'psql', '-U', 'presspilot_admin', '-d', 'presspilot', '-v', 'ON_ERROR_STOP=1', '-c', sql])
    run(compose + ['exec', '-T', 'db', 'pg_restore', '-U', 'presspilot_admin', '--clean', '--if-exists', '--exit-on-error', '-d', DATABASE], dump)
    run(compose + ['exec', '-T', 'api', 'python', '-c', EXTRACT], documents)
    validated = run(compose + ['exec', '-T', 'api', 'python', '-c', VALIDATE], json.dumps(fixture).encode())
    result = json.loads(validated.stdout.splitlines()[-1])
    result.update(synthetic=True, truncated_backup_rejected=True, archive_members=members,
                  backup_uploaded=False, production_restore=False)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
