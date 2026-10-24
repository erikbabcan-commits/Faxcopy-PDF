import os
from pathlib import Path
from sqlalchemy import update
from app.config import settings
from app.db import session_factory
from app.models import Job, Tenant
from app.worker import process_one
from app.reconciliation import reconcile_storage
from app.storage import job_dir


def test_preview_is_charged_and_purge_releases_both(client,account,upload):
    job=upload().json()
    assert process_one()
    preview=job_dir(account['tenant'].id,job['id'])/'preview.png'
    assert preview.stat().st_size>0
    assert client.get('/api/stats').json()['usage']['storage_bytes']==job['size_bytes']+preview.stat().st_size
    report=reconcile_storage()
    assert report['dry_run'] and not report['size_mismatches'] and not report['missing']
    assert report['tenants'][0]['difference_bytes']==0
    assert client.delete('/api/jobs/'+job['id'],headers=account['headers']).status_code==200
    assert client.get('/api/stats').json()['usage']['storage_bytes']==0


def test_preview_cannot_exceed_quota(client,account,upload):
    job=upload().json()
    with session_factory()() as db:
        db.execute(update(Tenant).where(Tenant.id==account['tenant'].id).values(storage_limit_bytes=job['size_bytes']));db.commit()
    assert process_one()
    detail=client.get('/api/jobs/'+job['id']).json()
    assert detail['status']=='review' and detail['preview_available'] is False
    assert not (job_dir(account['tenant'].id,job['id'])/'preview.png').exists()
    assert client.get('/api/stats').json()['usage']['storage_bytes']==job['size_bytes']


def test_reconciliation_reports_orphans_and_legacy_preview_without_changes(client,account,upload,tmp_path):
    job=upload().json();directory=job_dir(account['tenant'].id,job['id'])
    legacy=directory/'preview.png';legacy.write_bytes(b'synthetic-legacy')
    with session_factory()() as db:
        db.execute(update(Job).where(Job.id==job['id']).values(preview_available=True));db.commit()
    orphan=settings().data_dir/'.incoming'/'synthetic.part';orphan.parent.mkdir(exist_ok=True);orphan.write_bytes(b'synthetic-orphan')
    outside=tmp_path/'outside';outside.write_bytes(b'must-not-read')
    (settings().data_dir/'outside-link').symlink_to(outside)
    before={str(p.relative_to(settings().data_dir)):p.lstat().st_size for p in settings().data_dir.rglob('*')}
    report=reconcile_storage()
    after={str(p.relative_to(settings().data_dir)):p.lstat().st_size for p in settings().data_dir.rglob('*')}
    assert before==after and report['dry_run']
    assert '.incoming/synthetic.part' in report['untracked']
    assert 'outside-link' in report['unsafe_paths']
    assert report['size_mismatches'][0]['expected']==0


def test_preview_write_failure_does_not_charge_tenant(client,account,upload,monkeypatch):
    job=upload().json();original=Path.write_bytes
    def fail(self,data):
        if self.suffix=='.png':raise OSError('Synthetic disk failure')
        return original(self,data)
    monkeypatch.setattr(Path,'write_bytes',fail)
    assert process_one()
    assert client.get('/api/stats').json()['usage']['storage_bytes']==job['size_bytes']
    assert client.get('/api/jobs/'+job['id']).json()['preview_available'] is False
