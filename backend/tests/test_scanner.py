from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient
from app.schemas import PRESETS, ReviewIn

SAMPLE=Path(__file__).resolve().parents[2]/'samples'/'01-vizitka-kontrola.pdf'
TOKEN='test-scanner-token-no-production-use-0123456789'

@pytest.fixture
def scanner(monkeypatch):
    monkeypatch.setenv('SCANNER_TOKEN',TOKEN)
    from app.scanner_service import app
    with TestClient(app) as client:yield client

def test_scanner_requires_private_token(scanner):
    response=scanner.post('/scan',files={'file':('test.pdf',SAMPLE.read_bytes(),'application/pdf')},data={'rules':json.dumps(PRESETS[1][1])})
    assert response.status_code==401

def test_authenticated_scanner_returns_real_report(scanner):
    response=scanner.post('/scan',headers={'X-Scanner-Token':TOKEN},files={'file':('test.pdf',SAMPLE.read_bytes(),'application/pdf')},data={'rules':json.dumps(PRESETS[1][1])})
    assert response.status_code==200,response.text
    assert response.json()['report']['status']=='review'
    assert response.json()['report']['print_ready'] is False

def test_scanner_rejects_malformed_rules(scanner):
    response=scanner.post('/scan',headers={'X-Scanner-Token':TOKEN},files={'file':('test.pdf',SAMPLE.read_bytes(),'application/pdf')},data={'rules':'{"malicious":true}'})
    assert response.status_code==422

def test_blank_review_note_rejected():
    with pytest.raises(ValueError):ReviewIn(decision='accepted',note=' '*15,acknowledge_limits=True)
