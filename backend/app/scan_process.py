"""Short-lived parser process. Invoked with stripped environment, not by the API."""
import base64
import json
import os
import sys


def apply_limits():
    if sys.platform == "linux":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (12 * 1024**2, 12 * 1024**2))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)


def main():
    apply_limits()
    from .inspector import inspect_pdf
    source, profile_file = sys.argv[1:3]
    with open(source, "rb") as f:
        data = f.read(100 * 1024**2 + 1)
    with open(profile_file, encoding="utf-8") as f:
        rules = json.load(f)
    report = inspect_pdf(data, rules)
    preview = None
    if report["status"] in ("review", "blocked") and report.get("summary", {}).get("pages", 0) > 0:
        try:
            import io
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(source)
            page = doc[0]
            w, h = page.get_size()
            if w > 0 and h > 0:
                bitmap = page.render(scale=min(1.8, 1200 / max(w, h)), draw_annots=False)
                output = io.BytesIO()
                bitmap.to_pil().save(output, format="PNG", optimize=True)
                if output.tell() < 4 * 1024**2:
                    preview = base64.b64encode(output.getvalue()).decode("ascii")
                bitmap.close()
            page.close()
            doc.close()
        except Exception:
            report["preview_warning"] = "Náhľad sa nepodarilo vytvoriť. Nejde o tlačový nátlačok."
    print(json.dumps({"report": report, "preview_base64": preview}, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
