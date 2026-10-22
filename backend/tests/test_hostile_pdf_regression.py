"""Only generated, inert PDF bytes; never exercise an external target."""
import io
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject
from app.inspector import inspect_pdf
from app.schemas import PRESETS


@pytest.mark.parametrize("action", ["/JavaScript", "/Launch"])
def test_active_open_action_never_releases(action):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer._root_object[NameObject("/OpenAction")] = DictionaryObject({
        NameObject("/S"): NameObject(action),
        NameObject("/JS" if action == "/JavaScript" else "/F"): TextStringObject("inert synthetic fixture"),
    })
    output = io.BytesIO()
    writer.write(output)
    result = inspect_pdf(output.getvalue(), PRESETS[1][1])
    assert result["status"] in ("blocked", "error")
    assert result.get("release_allowed", False) is False


def test_truncated_object_graph_fails_closed():
    result = inspect_pdf(b"%PDF-1.7\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n", PRESETS[1][1])
    assert result["status"] == "error"
    assert result.get("release_allowed", False) is False
