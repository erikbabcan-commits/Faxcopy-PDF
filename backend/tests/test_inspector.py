from pathlib import Path
import math
import pytest
from app.inspector import inspect_pdf, image_dpi, matrix_mul, within, IDENTITY
from app.schemas import Rules, PRESETS, digest
from app.scanning import local_scan

SAMPLES = Path(__file__).resolve().parents[2] / 'samples'
RULES = PRESETS[1][1]

@pytest.mark.parametrize('filename,status,code',[
 ('01-vizitka-kontrola.pdf','review',None),
 ('02-chybajuca-spadavka.pdf','blocked','BLEED_TOO_SMALL'),
 ('03-nizke-rozlisenie.pdf','blocked','IMAGE_LOW_DPI'),
 ('04-nevlozeny-font.pdf','blocked','FONT_NOT_EMBEDDED'),
 ('05-aktivny-obsah.pdf','blocked','ACTIVE_CONTENT'),
 ('06-poskodeny-subor.pdf','error','PDF_PARSE_FAILED'),
 ('07-sifrovany.pdf','blocked','PDF_ENCRYPTED'),
 ('08-deklaracia-pdfx.pdf','review','PDFX_DECLARATION_ONLY'),
])
def test_synthetic_pdf_results(filename,status,code):
    report = inspect_pdf((SAMPLES/filename).read_bytes(), RULES)
    assert report['status']==status
    assert report['print_ready'] is False and report['release_allowed'] is False
    if code:
        assert code in [f['code'] for f in report.get('findings',[])] or report.get('error_code') == code

@pytest.mark.parametrize('filename', ['01-vizitka-kontrola.pdf','02-chybajuca-spadavka.pdf','03-nizke-rozlisenie.pdf','04-nevlozeny-font.pdf','08-deklaracia-pdfx.pdf'])
def test_report_reproducibility(filename):
    data=(SAMPLES/filename).read_bytes()
    assert digest(inspect_pdf(data,RULES))==digest(inspect_pdf(data,RULES))

@pytest.mark.parametrize('matrix,width,height,unit,expected',[
 ((72,0,0,72,0,0),300,300,1,300),
 ((144,0,0,144,0,0),300,300,1,150),
 ((0,72,-72,0,30,80),300,300,1,300),
 ((72,0,0,72,0,0),300,300,2,150),
 ((72,0,0,144,0,0),300,600,1,300),
])
def test_physical_image_resolution(matrix,width,height,unit,expected):
    assert image_dpi(matrix,width,height,unit)==pytest.approx(expected)

def test_nested_transform_is_included():
    outer=(2,0,0,2,0,0)
    inner=(72,0,0,72,10,10)
    assert image_dpi(matrix_mul(outer,inner),300,300)==pytest.approx(150)

def test_matrix_identity():
    m=(10,3,4,15,8,12)
    assert matrix_mul(IDENTITY,m)==m and matrix_mul(m,IDENTITY)==m

def test_skew_uses_worst_direction():
    assert image_dpi((72,0,72,72,0,0),300,300)<300

@pytest.mark.parametrize('m',[(0,0,0,0,0,0),(float('nan'),0,0,72,0,0)])
def test_degenerate_transform_rejected(m):
    with pytest.raises(ValueError): image_dpi(m,300,300)

def test_geometry_containment():
    assert within([3,3,85,55],[0,0,91,61])
    assert not within([-3,0,85,55],[0,0,91,61])

def test_incomplete_dimension_profile_rejected():
    with pytest.raises(ValueError): Rules(trim_width_mm=85)

def test_unknown_profile_fields_rejected():
    with pytest.raises(ValueError): Rules(auto_release=True)

def test_invalid_page_range_rejected():
    with pytest.raises(ValueError): Rules(min_pages=10,max_pages=2)

def test_profile_dimensions_checked():
    rules={**RULES,'trim_width_mm':90}
    assert 'TRIM_SIZE_MISMATCH' in [x['code'] for x in inspect_pdf((SAMPLES/'01-vizitka-kontrola.pdf').read_bytes(),rules)['findings']]

def test_scan_subprocess_and_real_preview():
    result=local_scan(SAMPLES/'01-vizitka-kontrola.pdf',RULES)
    assert result['report']['status']=='review'
    assert result['preview_base64'].startswith('iVBOR')

def test_plain_text_is_never_a_pdf_success():
    assert inspect_pdf(b'hello',RULES)['status']=='error'
