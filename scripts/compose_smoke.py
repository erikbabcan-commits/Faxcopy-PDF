"""Disposable Compose CI probe. Refuses every project name except its synthetic test project."""
import json
import subprocess

PROJECT = "synthetic-faxcopy-ci"

PROBE = r'''
import hashlib,http.client,json,secrets,time,uuid
from app.db import session_factory
from app.manage import provision
from pathlib import Path
password=secrets.token_urlsafe(32)
with session_factory()() as db:
    tenant,user=provision(db,'Synthetic Compose CI','compose@example.test',password)
origin='http://localhost:8080'
cookie='';csrf=''
def request(method,path,body=None,extra=None):
    c=http.client.HTTPConnection('127.0.0.1',8080,timeout=10)
    headers={'Origin':origin}
    if cookie:headers['Cookie']=cookie
    if csrf:headers['X-CSRF-Token']=csrf
    if isinstance(body,dict):body=json.dumps(body).encode();headers['Content-Type']='application/json'
    if extra:headers.update(extra)
    c.request(method,path,body=body,headers=headers)
    r=c.getresponse();data=r.read();status=r.status;response_headers=dict(r.getheaders());c.close()
    return status,data,response_headers
status,data,h=request('POST','/api/auth/login',{'workspace_id':tenant.id,'email':user.email,'password':password})
assert status==200,status
csrf=json.loads(data)['csrf_token'];cookie=h['set-cookie'].split(';',1)[0]
status,data,_=request('GET','/api/profiles');assert status==200
profile=next(p for p in json.loads(data) if p['name'].startswith('Vizitka'))
pdf=Path('/app/samples/01-vizitka-kontrola.pdf').read_bytes();boundary='synthetic-'+uuid.uuid4().hex
body=(f'--{boundary}\r\nContent-Disposition: form-data; name="profile_id"\r\n\r\n{profile["id"]}\r\n'
      f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+pdf+f'\r\n--{boundary}--\r\n'.encode()
status,data,_=request('POST','/api/jobs',body,{'Content-Type':'multipart/form-data; boundary='+boundary,'Idempotency-Key':str(uuid.uuid4())})
assert status==201,status
job=json.loads(data)
for _ in range(120):
    status,data,_=request('GET','/api/jobs/'+job['id']);detail=json.loads(data)
    if detail['status'] not in ('queued','processing'):break
    time.sleep(.5)
assert detail['status']=='review',detail.get('error_code')
assert detail['preview_available'] and detail['report']['release_allowed'] is False
assert detail['sha256']==hashlib.sha256(pdf).hexdigest()
status,preview,_=request('GET','/api/jobs/'+job['id']+'/preview');assert status==200
status,data,_=request('GET','/api/stats');assert json.loads(data)['usage']['storage_bytes']==len(pdf)+len(preview)
status,data,_=request('POST','/api/jobs/'+job['id']+'/review',{'decision':'accepted','note':'Synthetic internal handoff only','acknowledge_limits':True});assert status==200
print(json.dumps({'status':'passed','flow':'API -> PostgreSQL -> worker -> private scanner -> preview -> manual handoff','synthetic':True,'print_release':False}))
'''

if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',choices=[PROJECT],required=True)
    args=parser.parse_args()
    subprocess.run(['docker','compose','-p',args.project,'exec','-T','api','python','-'],input=PROBE,text=True,check=True)
