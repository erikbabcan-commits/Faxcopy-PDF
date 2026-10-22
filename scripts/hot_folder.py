"""One-pass hot-folder client. Uploads only; never modifies PDFs or accepts jobs.
Run from a scheduler. Files should be atomically moved into the watched folder
by the producer. The SQLite ledger persists one idempotency key per payload.
"""
import argparse
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import time
import uuid
from urllib.parse import urlsplit
import httpx


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--url',required=True)
    parser.add_argument('--profile',required=True)
    parser.add_argument('--ledger',type=Path,default=Path('.presspilot-hotfolder.db'))
    args=parser.parse_args()
    token=os.getenv('PRESSPILOT_API_KEY','')
    if not token.startswith('pp_'):parser.error('Set PRESSPILOT_API_KEY to an upload-scoped key')
    url=urlsplit(args.url)
    if url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('localhost','127.0.0.1')):
        parser.error('HTTPS is required except for localhost')
    if url.username or url.password or url.query or url.fragment:parser.error('Use a clean base URL')
    if not args.folder.is_dir():parser.error('Folder does not exist')
    os.umask(0o077)
    with sqlite3.connect(args.ledger,timeout=30) as db, httpx.Client(timeout=120,follow_redirects=False,trust_env=False) as client:
        db.execute('CREATE TABLE IF NOT EXISTS sent (fingerprint TEXT PRIMARY KEY, token TEXT NOT NULL, job_id TEXT)')
        failed=False
        for path in sorted(args.folder.glob('*.pdf')):
            if path.is_symlink() or time.time()-path.stat().st_mtime<10:continue
            # Bound memory; copy to a temporary spool to prevent producer changes during upload.
            if path.stat().st_size>25*1024**2:
                print(f'Skipped oversize file: {path.name}',file=sys.stderr);failed=True;continue
            import tempfile
            with tempfile.TemporaryFile() as spool:
                checksum=hashlib.sha256();size=0
                with path.open('rb') as source:
                    while chunk:=source.read(1024**2):
                        size+=len(chunk)
                        if size>25*1024**2:break
                        checksum.update(chunk);spool.write(chunk)
                if size>25*1024**2:
                    print(f'File grew beyond limit: {path.name}',file=sys.stderr);failed=True;continue
                fp=hashlib.sha256((args.url+'|'+args.profile+'|'+str(path.resolve())+'|'+checksum.hexdigest()).encode()).hexdigest()
                db.execute('INSERT OR IGNORE INTO sent (fingerprint,token) VALUES (?,?)',(fp,str(uuid.uuid4())));db.commit()
                key,job_id=db.execute('SELECT token,job_id FROM sent WHERE fingerprint=?',(fp,)).fetchone()
                if job_id:continue
                spool.seek(0)
                try:
                    response=client.post(args.url.rstrip('/')+'/api/jobs',headers={'Authorization':'Bearer '+token,'Idempotency-Key':key},
                        files={'file':(path.name,spool,'application/pdf')},data={'profile_id':args.profile,'order_ref':path.stem[:100]})
                    response.raise_for_status();result=response.json()
                    db.execute('UPDATE sent SET job_id=? WHERE fingerprint=?',(result['id'],fp));db.commit()
                    print(f"Queued {path.name}: {result['id']}")
                except (httpx.HTTPError,ValueError,KeyError):
                    print(f'Upload failed: {path.name}. Retry preserves its idempotency key.',file=sys.stderr);failed=True
        return 1 if failed else 0

if __name__=='__main__':sys.exit(main())
