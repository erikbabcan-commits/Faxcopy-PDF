"""Real HTTP smoke: API + worker + scanner subprocesses; disposable local data.
This verifies transport and processing, not Docker isolation or browser behavior.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));return s.getsockname()[1]


def main():
    processes=[];logfiles=[];checks=[]
    with tempfile.TemporaryDirectory(prefix='pp-http-test-') as tmp:
        root=Path(tmp);api_port,scanner_port=free_port(),free_port()
        origin=f'http://127.0.0.1:{api_port}'
        os.environ.update(APP_ENV='test',APP_ORIGIN=origin,DATABASE_URL=f'sqlite:///{root/"app.db"}',DATA_DIR=str(root/'data'),STATIC_DIR=str(ROOT/'frontend'/'dist'),SECURE_COOKIES='false',SCANNER_URL=f'http://127.0.0.1:{scanner_port}',SCANNER_TOKEN=secrets.token_hex(32),LLM_BASE_URL='',LLM_MODEL='')
        from app.manage import migrate,provision
        from app.db import session_factory
        migrate();password=secrets.token_urlsafe(24)
        with session_factory()() as db:tenant,user=provision(db,'HTTP test print shop','qa@example.test',password)
        try:
            commands=[
                ['-m','uvicorn','app.scanner_service:app','--host','127.0.0.1','--port',str(scanner_port),'--no-access-log'],
                ['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(api_port),'--no-access-log'],
                ['-m','app.worker'],
            ]
            for i,command in enumerate(commands):
                logfile=(root/f'service-{i}.log').open('w');logfiles.append(logfile)
                processes.append(subprocess.Popen([sys.executable,*command],cwd=ROOT/'backend',env=os.environ.copy(),stdout=logfile,stderr=logfile))
            with httpx.Client(base_url=origin,timeout=20,trust_env=False) as client:
                for attempt in range(120):
                    try:
                        if client.get('/readyz').status_code==200 and httpx.get(f'http://127.0.0.1:{scanner_port}/healthz',timeout=1,trust_env=False).status_code==200:break
                    except httpx.HTTPError:pass
                    if any(p.poll() is not None for p in processes):raise RuntimeError('Service exited')
                    time.sleep(.2)
                else:raise RuntimeError('Startup timeout')
                login=client.post('/api/auth/login',headers={'Origin':origin},json={'workspace_id':tenant.id,'email':user.email,'password':password})
                login.raise_for_status();headers={'Origin':origin,'X-CSRF-Token':login.json()['csrf_token']}
                checks.append('HTTP login and server session')
                profile=next(p for p in client.get('/api/profiles').json() if p['name'].startswith('Vizitka'))
                expected={'01-vizitka-kontrola.pdf':'review','02-chybajuca-spadavka.pdf':'blocked','06-poskodeny-subor.pdf':'error'}
                valid_job=None
                for filename,status in expected.items():
                    source=ROOT/'samples'/filename
                    response=client.post('/api/jobs',headers={**headers,'Idempotency-Key':str(uuid.uuid4())},files={'file':(filename,source.read_bytes(),'application/pdf')},data={'profile_id':profile['id'],'order_ref':'HTTP-SMOKE'})
                    response.raise_for_status();job=response.json()
                    for _ in range(200):
                        detail=client.get('/api/jobs/'+job['id']).json()
                        if detail['status'] not in ('queued','processing'):break
                        time.sleep(.1)
                    assert detail['status']==status,detail
                    assert detail['report']['print_ready'] is False and detail['report']['release_allowed'] is False
                    checks.append(f'HTTP upload > DB queue > worker > private scanner HTTP > {status}: {filename}')
                    if status=='review':valid_job=detail
                assert valid_job
                preview=client.get(f"/api/jobs/{valid_job['id']}/preview")
                assert preview.status_code==200 and preview.content.startswith(b'\x89PNG')
                original=client.get(f"/api/jobs/{valid_job['id']}/original")
                assert hashlib.sha256(original.content).hexdigest()==valid_job['sha256']
                checks.append('HTTP raster preview + original hash integrity')
                review=client.post(f"/api/jobs/{valid_job['id']}/review",headers=headers,json={'decision':'accepted','note':'Internal DTP handoff only, no print approval.','acknowledge_limits':True})
                review.raise_for_status()
                assert review.json()['decision']=='accepted' and review.json()['report']['release_allowed'] is False
                assert client.get('/api/stats').json()['accepted']==1
                checks.append('HTTP manual DTP handoff retains false release flag')
            result={'status':'passed','checks':checks,'passed':len(checks),'transport':'real localhost HTTP','services':['api','worker','scanner'],'database':'SQLite','limitations':['Not Docker isolation','Not PostgreSQL','Not browser interaction','Not malicious PDF security audit']}
            target=ROOT/'docs'/'http-results.json';target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
        finally:
            for p in processes:
                if p.poll() is None:p.terminate()
            for p in processes:
                try:p.wait(timeout=10)
                except subprocess.TimeoutExpired:p.kill();p.wait()
            for f in logfiles:f.close()

if __name__=='__main__':main()
