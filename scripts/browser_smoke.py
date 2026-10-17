"""Real browser smoke against disposable SQLite + API + worker; no mocked API.
Run after installing backend/requirements-dev.txt and `playwright install chromium`.
System Chromium is used if available. Only synthetic fixtures are uploaded.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def wait_ready(url,process):
    for _ in range(150):
        if process.poll() is not None:
            raise RuntimeError('API exited before becoming healthy')
        try:
            with urllib.request.urlopen(url+'/readyz',timeout=1) as response:
                if response.status==200:return
        except Exception:pass
        time.sleep(.2)
    raise RuntimeError('API startup timed out')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--screenshots',type=Path,default=ROOT/'docs'/'screenshots')
    parser.add_argument('--report',type=Path,default=ROOT/'docs'/'browser-results.json')
    args=parser.parse_args()
    args.screenshots.mkdir(parents=True,exist_ok=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pp-browser-') as temp:
        folder=Path(temp)
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        origin=f'http://127.0.0.1:{port}'
        os.environ.update(APP_ENV='test',APP_ORIGIN=origin,DATABASE_URL=f'sqlite:///{folder/"app.db"}',DATA_DIR=str(folder/'data'),STATIC_DIR=str(ROOT/'frontend'/'dist'),SECURE_COOKIES='false',SCANNER_URL='',LLM_BASE_URL='',LLM_MODEL='')
        from app.manage import migrate,provision,seed_demo
        from app.db import session_factory
        from app.worker import process_one,heartbeat
        migrate()
        password=secrets.token_urlsafe(26)
        with session_factory()() as db:tenant,user=provision(db,'North Print Studio','operator@example.test',password)
        seed_demo(tenant.id,ROOT/'samples')
        while process_one():pass
        heartbeat('browser-test-worker')
        api_log=(folder/'api.log').open('w')
        server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=ROOT/'backend',env=os.environ.copy(),stdout=api_log,stderr=api_log)
        worker_log=(folder/'worker.log').open('w')
        worker=subprocess.Popen([sys.executable,'-m','app.worker'],cwd=ROOT/'backend',env=os.environ.copy(),stdout=worker_log,stderr=worker_log)
        checks=[];errors=[];overflows=[]
        try:
            wait_ready(origin,server)
            from playwright.sync_api import sync_playwright,expect
            with sync_playwright() as p:
                executable=shutil.which('chromium') or shutil.which('chromium-browser')
                browser=p.chromium.launch(headless=True,executable_path=executable)
                context=browser.new_context(viewport={'width':1440,'height':1100},device_scale_factor=1)
                page=context.new_page()
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(origin,wait_until='networkidle')
                expect(page.locator('#login-form')).to_be_visible()
                page.screenshot(path=str(args.screenshots/'01-login-desktop.png'),full_page=True)
                page.locator('[name=workspace_id]').fill(tenant.id)
                page.locator('[name=email]').fill(user.email)
                page.locator('[name=password]').fill(password)
                page.get_by_role('button',name='Prihlásiť sa',exact=True).click()
                expect(page.get_by_role('heading',name='Každý podklad pod kontrolou.')).to_be_visible()
                expect(page.locator('.metric').first.locator('strong')).to_have_text('8')
                page.screenshot(path=str(args.screenshots/'02-dashboard-desktop.png'),full_page=True)
                checks.append('login + real dashboard + eight processed fixtures')
                page.locator('.nav-item[href="#jobs"]').click()
                expect(page.get_by_role('heading',name='Zákazky',exact=True)).to_be_visible()
                page.locator('.row-link',has_text='02-chybajuca-spadavka.pdf').click()
                expect(page.get_by_text('BLEED_TOO_SMALL',exact=True)).to_be_visible()
                expect(page.get_by_text('PDF metadata',exact=True)).to_be_visible()
                expect(page.get_by_role('button',name='Prevziať na DTP')).to_have_count(0)
                checks.append('blocked job findings + cannot accept known errors')
                page.get_by_role('button',name='Vytvoriť návrh správy').click()
                expect(page.locator('#assistant-output textarea')).to_be_visible()
                assert 'spadávka' in page.locator('#assistant-output textarea').input_value()
                checks.append('real rule-based DTP assistant')
                page.screenshot(path=str(args.screenshots/'03-job-detail-desktop.png'),full_page=True)
                page.locator('.nav-item[href="#profiles"]').click()
                expect(page.get_by_role('heading',name='Výrobné profily',exact=True)).to_be_visible()
                expect(page.locator('.profile-card')).to_have_count(3)
                page.get_by_role('button',name='Vytvoriť profil').click()
                page.locator('#profile-form [name=name]').fill('Browser fixture profile')
                page.locator('#profile-form [name=bleed_mm]').fill('0')
                page.locator('#profile-form button').last.click()
                expect(page.locator('.profile-card')).to_have_count(4)
                checks.append('profile creation + persisted server data')
                page.locator('.nav-item[href="#home"]').click()
                page.get_by_role('button',name='Nová kontrola').click()
                page.locator('#file-input').set_input_files(ROOT/'samples'/'01-vizitka-kontrola.pdf')
                select=page.locator('#upload-form [name=profile_id]')
                select.select_option(label='Vizitka · 85 × 55 mm · v1')
                page.locator('#upload-form [name=order_ref]').fill('BROWSER-E2E-REAL')
                page.get_by_role('button',name='Nahrať a skontrolovať').click()
                expect(page.get_by_role('heading',name='01-vizitka-kontrola.pdf',exact=True)).to_be_visible(timeout=15000)
                expect(page.get_by_role('button',name='Prevziať na DTP')).to_be_visible(timeout=25000)
                page.locator('#review-form [name=note]').fill('Prevzaté na odbornú kontrolu; bez uvoľnenia do výroby.')
                page.locator('#review-form [name=acknowledge]').check()
                page.get_by_role('button',name='Prevziať na DTP').click()
                expect(page.locator('.review-record')).to_be_visible()
                expect(page.locator('.review-record .badge')).to_have_text('Prevzaté DTP')
                checks.append('real file upload > worker > raster preview > manual DTP decision')
                with page.expect_download() as download:
                    page.get_by_role('link',name='JSON report').click()
                artifact=download.value
                report=json.loads(Path(artifact.path()).read_text())
                assert report['job']['report']['print_ready'] is False
                assert report['job']['decision']=='accepted'
                checks.append('downloaded real JSON report preserves print-ready boundary')
                page.locator('.nav-item[href="#settings"]').click()
                expect(page.get_by_role('heading',name='Nastavenia',exact=True)).to_be_visible()
                page.get_by_role('button',name='Nový kľúč').click()
                page.locator('#key-form [name=name]').fill('Browser API key')
                page.get_by_role('button',name='Vygenerovať kľúč').click()
                expect(page.locator('#key-value')).to_be_visible()
                assert page.locator('#key-value').input_value().startswith('pp_')
                page.get_by_role('button',name='Zavrieť',exact=True).click()
                expect(page.get_by_role('cell',name='Browser API key',exact=True)).to_be_visible()
                checks.append('scoped API key generation')
                page.locator('.nav-item[href="#audit"]').click()
                expect(page.get_by_role('heading',name='Auditná stopa',exact=True)).to_be_visible()
                expect(page.locator('.audit-item').first).to_be_visible()
                checks.append('audit timeline from real events')
                for width in [360,390,430,932]:
                    page.set_viewport_size({'width':width,'height':932 if width<900 else 430})
                    page.goto(origin+'/#home',wait_until='networkidle')
                    expect(page.get_by_role('heading',name='Každý podklad pod kontrolou.')).to_be_visible()
                    dimensions=page.evaluate('({viewport: innerWidth, content: document.documentElement.scrollWidth})')
                    if dimensions['content']>dimensions['viewport']+1:overflows.append({'width':width,**dimensions})
                    page.screenshot(path=str(args.screenshots/f'04-dashboard-{width}.png'),full_page=True)
                    if width==430:
                        page.get_by_role('button',name='Zobraziť navigáciu').click()
                        expect(page.locator('.sidebar.visible')).to_be_visible()
                        page.locator('.nav-item[href="#jobs"]').click()
                        expect(page.get_by_role('heading',name='Zákazky',exact=True)).to_be_visible()
                        checks.append('mobile menu and real job list')
                checks.append('responsive viewport checks at 360, 390, 430 and 932 pixels')
                assert not overflows,overflows
                assert not errors,errors
                checks.append('no uncaught JavaScript errors')
                browser.close()
            result={'status':'passed','checks':checks,'passed':len(checks),'javascript_errors':errors,'horizontal_overflows':overflows,'database':'SQLite','scanner':'local resource-limited subprocess','browser':'Chromium','note':'Synthetic fixtures, real API/worker. Not a load test, security audit, Docker test or PDF/X certification.'}
            args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(result,ensure_ascii=False,indent=2))
        except Exception as exc:
            reason = str(exc)
            args.report.write_text(json.dumps({'status': 'blocked' if 'ERR_BLOCKED_BY_ADMINISTRATOR' in reason else 'failed',
                'passed_checks': checks, 'reason': reason[:1200],
                'note': 'Do not interpret this as a successful end-to-end test.'}, ensure_ascii=False, indent=2), encoding='utf-8')
            api_log.flush();worker_log.flush()
            print((folder/'api.log').read_text()[-6000:],file=sys.stderr)
            raise
        finally:
            for process in (worker,server):
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            api_log.close();worker_log.close()

if __name__=='__main__':main()
