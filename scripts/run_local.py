"""Local trusted-file pilot launcher. Does not publish any public URL."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8080)
    commands=parser.add_subparsers(dest='command',required=True)
    init=commands.add_parser('init',help='Migrate local database and create a workspace')
    init.add_argument('--workspace',required=True)
    init.add_argument('--email',required=True)
    init.add_argument('--seed-demo',action='store_true',help='Queue eight clearly labelled synthetic PDFs')
    commands.add_parser('serve',help='Start API + worker on loopback only; Ctrl+C stops both')
    args=parser.parse_args()
    if not 1024 <= args.port <= 65535:parser.error('Port must be between 1024 and 65535')
    os.umask(0o077)
    local=ROOT/'.local';local.mkdir(exist_ok=True)
    # This launcher always uses a dedicated local pilot, never a production .env.
    os.environ.update(APP_ENV='pilot',APP_ORIGIN=f'http://localhost:{args.port}',
        DATABASE_URL='sqlite:///'+str(local/'presspilot.db'),DATA_DIR=str(local/'data'),
        STATIC_DIR=str(ROOT/'frontend'/'dist'),SECURE_COOKIES='false',SCANNER_URL='',SCANNER_TOKEN='',
        LLM_BASE_URL='',LLM_MODEL='')
    sys.path.insert(0,str(ROOT/'backend'))
    try:
        from app.manage import migrate,provision,seed_demo
        from app.db import session_factory
    except ImportError as exc:
        print(f'Missing dependency: {exc}. Install: python -m pip install -r backend/requirements.txt',file=sys.stderr)
        return 1
    if args.command=='init':
        import getpass
        migrate()
        password=getpass.getpass('Owner password (at least 12 characters): ')
        if password!=getpass.getpass('Repeat password: '):parser.error('Passwords do not match')
        with session_factory()() as db:
            tenant,user=provision(db,args.workspace,args.email,password)
        identity=json.dumps({'workspace_id':tenant.id,'workspace':tenant.name,'email':user.email},ensure_ascii=False,indent=2)
        (local/'workspace.json').write_text(identity+'\n',encoding='utf-8')
        print(identity)
        print('Login details saved to .local/workspace.json (password is not stored there).')
        if args.seed_demo:seed_demo(tenant.id,ROOT/'samples')
        print('Save the workspace ID. Next: python scripts/run_local.py serve')
        return 0
    if not (local/'presspilot.db').exists():parser.error('Initialize first: python scripts/run_local.py init --workspace "My print shop" --email "owner@example.com"')
    if not (ROOT/'frontend'/'dist'/'index.html').exists():parser.error('Frontend is missing. Run npm run build in frontend/.')
    try:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            probe.bind(('127.0.0.1',args.port))
    except OSError:
        parser.error(f'Port {args.port} is unavailable. Stop the existing instance or use --port 8081 serve.')
    migrate()
    commands=[
        [sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(args.port),'--no-proxy-headers','--no-access-log'],
        [sys.executable,'-m','app.worker'],
    ]
    processes=[]
    try:
        for command in commands:processes.append(subprocess.Popen(command,cwd=ROOT/'backend',env=os.environ.copy()))
        print(f'\nPressPilot: http://localhost:{args.port}\nLocal trusted-file pilot only. Ctrl+C stops API and worker.\n',flush=True)
        while all(p.poll() is None for p in processes):time.sleep(.5)
        print('A service stopped. Inspect the error above.',file=sys.stderr)
        return 1
    except KeyboardInterrupt:return 0
    finally:
        for process in processes:
            if process.poll() is None:process.terminate()
        for process in processes:
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=='__main__':sys.exit(main())
