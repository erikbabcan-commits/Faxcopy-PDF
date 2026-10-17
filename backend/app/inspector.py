"""Conservative structural PDF inspection. Not a PDF/X conformance validator.

Only call in the resource-limited scan subprocess. No modifications are written.
Effective image resolution uses the full placement transform, including nested
Form XObjects and UserUnit; clipping, patterns and visual bleed are not certified.
"""
import hashlib
import io
import math
from collections import Counter
from importlib.metadata import version
from pypdf import PdfReader
from pypdf.generic import ContentStream, IndirectObject, DictionaryObject, ArrayObject
from .schemas import Rules, digest

ENGINE_VERSION = "0.1.0"
MAX_OPERATIONS = 150_000
MAX_OBJECTS = 40_000
MAX_FINDINGS = 1000
IDENTITY = (1., 0., 0., 1., 0., 0.)
COVERAGE = {
    "page_geometry": "Physical page boxes, dimensions, rotation and UserUnit",
    "geometric_bleed": "Box margins only; actual artwork coverage NOT verified",
    "font_embedding": "Presence of embedded font programs; glyph correctness NOT verified",
    "image_dpi": "Placed image/inline-image resolution, including nested Form transforms",
    "color_inventory": "Basic color-space inventory; no ICC conversion or color proof",
    "pdfx_conformance": "NOT IMPLEMENTED: metadata declarations are not validation",
    "overprint_correctness": "NOT IMPLEMENTED: basic presence detection only",
    "transparency_correctness": "NOT IMPLEMENTED: basic presence detection only",
    "visual_bleed": "NOT IMPLEMENTED",
    "ink_coverage_trapping_binding": "NOT IMPLEMENTED",
    "malware_cleanliness": "NOT CERTIFIED: active-content flags are not antivirus",
}


class InspectionLimit(Exception):
    pass


def obj(value):
    return value.get_object() if hasattr(value, "get_object") else value


def matrix_mul(a, b):
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def image_dpi(matrix, width, height, user_unit=1.):
    a, b, c, d, _, _ = matrix
    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions")
    sx, sy = (a*a+b*b)/(width*width), (c*c+d*d)/(height*height)
    cross = (a*c+b*d)/(width*height)
    eigen = (sx+sy+math.sqrt((sx-sy)**2+4*cross*cross))/2
    if not math.isfinite(eigen) or eigen <= 1e-20:
        raise ValueError("Degenerate image transform")
    return 72./(math.sqrt(eigen)*user_unit)


def box(value):
    coordinates = [float(n) for n in obj(value)]
    if len(coordinates) != 4 or not all(math.isfinite(n) and abs(n) <= 1e7 for n in coordinates):
        raise ValueError("Invalid box")
    if coordinates[2] <= coordinates[0] or coordinates[3] <= coordinates[1]:
        raise ValueError("Inverted or empty box")
    return coordinates


def within(inner, outer, eps=0.01):
    return inner[0] >= outer[0]-eps and inner[1] >= outer[1]-eps and inner[2] <= outer[2]+eps and inner[3] <= outer[3]+eps


class Inspector:
    def __init__(self, data: bytes, rules: dict):
        self.data = data
        self.rules = Rules.model_validate(rules)
        self.findings = []
        self.seen_findings = set()
        self.pages = []
        self.images = []
        self.fonts = []
        self.colors = set()
        self.operation_count = 0
        self.checked_fonts = set()
        self.reader = None

    def add(self, code, severity, message, page=None, evidence=None):
        item = {"code": code, "severity": severity, "message": message, "page": page, "evidence": evidence or {}}
        key = digest(item)
        if key in self.seen_findings:
            return
        if len(self.findings) >= MAX_FINDINGS:
            raise InspectionLimit("Too many findings")
        self.seen_findings.add(key)
        self.findings.append(item)

    def color(self, value, resources):
        value = obj(value)
        name = str(value)
        simple = {"/DeviceRGB": "RGB", "/RGB": "RGB", "/DeviceCMYK": "CMYK", "/CMYK": "CMYK", "/DeviceGray": "Gray", "/G": "Gray"}
        if name in simple:
            return simple[name]
        if isinstance(value, (ArrayObject, list)) and value:
            mode = str(value[0])
            if mode == "/ICCBased":
                n = int(obj(value[1]).get("/N", 0))
                return {1: "ICC Gray", 3: "ICC RGB", 4: "ICC CMYK"}.get(n, "ICC Unknown")
            if mode == "/Indexed":
                return "Indexed " + self.color(value[1], {})
            return mode.lstrip("/")
        spaces = obj(resources.get("/ColorSpace", {}))
        if name in spaces:
            resolved = obj(spaces[name])
            if str(resolved) != name:
                return self.color(resolved, {})
        return "Unknown" if not value else name.lstrip("/")[:50]

    def check_font(self, font_ref, page_no, name):
        font = obj(font_ref)
        key = (page_no, name, str(getattr(font_ref, "idnum", "direct")))
        if key in self.checked_fonts:
            return
        self.checked_fonts.add(key)
        subtype = str(font.get("/Subtype", ""))
        base = str(font.get("/BaseFont", name))[:150]
        targets = obj(font.get("/DescendantFonts", [])) if subtype == "/Type0" else [font]
        present = bool(targets)
        for target in targets:
            descriptor = obj(obj(target).get("/FontDescriptor", {}))
            present = present and any(descriptor.get(k) is not None for k in ("/FontFile", "/FontFile2", "/FontFile3"))
        if subtype == "/Type3":
            present = bool(font.get("/CharProcs"))
            self.add("TYPE3_FONT_REVIEW", "warning", "Type 3 font vyžaduje odbornú kontrolu vykreslenia.", page_no, {"font": base})
        self.fonts.append({"page": page_no, "name": base, "subtype": subtype, "embedded_program_present": bool(present)})
        if not present and self.rules.require_embedded_fonts:
            self.add("FONT_NOT_EMBEDDED", "error", "Použitý font nemá vložený fontový program.", page_no, {"font": base})

    def walk_content(self, stream, resources, page_no, unit, matrix=IDENTITY, depth=0, active=frozenset()):
        if depth > 12:
            raise InspectionLimit("Form nesting limit")
        resources = obj(resources)
        stack = []
        content = ContentStream(stream, self.reader)
        for operands, operation in content.operations:
            self.operation_count += 1
            if self.operation_count > MAX_OPERATIONS:
                raise InspectionLimit("Content operation limit")
            if operation == b"q":
                stack.append(matrix)
                if len(stack) > 100:
                    raise InspectionLimit("Graphics stack limit")
            elif operation == b"Q":
                if not stack:
                    self.add("GRAPHICS_STACK_INVALID", "error", "Neplatný zásobník grafického stavu.", page_no)
                else:
                    matrix = stack.pop()
            elif operation == b"cm":
                values = tuple(float(n) for n in operands)
                if len(values) != 6 or not all(math.isfinite(n) and abs(n) < 1e9 for n in values):
                    raise ValueError("Invalid transform")
                matrix = matrix_mul(matrix, values)
            elif operation == b"Tf":
                fonts = obj(resources.get("/Font", {}))
                name = str(operands[0])
                if name not in fonts:
                    self.add("FONT_RESOURCE_MISSING", "error", "Chýba odkazovaný fontový zdroj.", page_no)
                else:
                    self.check_font(fonts.raw_get(name) if hasattr(fonts, "raw_get") else fonts[name], page_no, name)
            elif operation in (b"rg", b"RG"):
                self.colors.add("RGB")
            elif operation in (b"k", b"K"):
                self.colors.add("CMYK")
            elif operation in (b"g", b"G"):
                self.colors.add("Gray")
            elif operation in (b"cs", b"CS") and operands:
                self.colors.add(self.color(operands[0], resources))
            elif operation == b"gs":
                states = obj(resources.get("/ExtGState", {}))
                state = obj(states.get(str(operands[0]), {}))
                if bool(state.get("/OP", False)) or bool(state.get("/op", False)):
                    self.add("OVERPRINT_PRESENT", "warning", "Zistený overprint; jeho správnosť musí overiť DTP operátor.", page_no)
                if float(state.get("/CA", 1)) < 1 or float(state.get("/ca", 1)) < 1 or str(state.get("/SMask", "/None")) != "/None":
                    self.add("TRANSPARENCY_PRESENT", "warning", "Zistená priehľadnosť alebo maska; bez kontroly výrobného RIP.", page_no)
            elif operation in (b"sh", b"SCN", b"scn"):
                self.add("PATTERN_SHADING_REVIEW", "warning", "Vzory alebo shading nie sú plne pokryté základným inšpektorom.", page_no)
            elif operation == b"INLINE IMAGE":
                image = operands.get("settings", {})
                self.inspect_image(image, matrix, page_no, unit, resources, inline=True)
            elif operation == b"Do":
                xobjects = obj(resources.get("/XObject", {}))
                name = str(operands[0])
                if name not in xobjects:
                    self.add("XOBJECT_MISSING", "error", "Chýba odkazovaný grafický objekt.", page_no)
                    continue
                reference = xobjects.raw_get(name) if hasattr(xobjects, "raw_get") else xobjects[name]
                item = obj(reference)
                subtype = str(item.get("/Subtype", ""))
                if subtype == "/Image":
                    self.inspect_image(item, matrix, page_no, unit, resources)
                elif subtype == "/Form":
                    ident = (getattr(reference, "idnum", id(item)), getattr(reference, "generation", 0))
                    if ident in active:
                        raise InspectionLimit("Cyclic Form XObject")
                    local = tuple(float(n) for n in obj(item.get("/Matrix", IDENTITY)))
                    if len(local) != 6 or not all(math.isfinite(n) for n in local):
                        raise ValueError("Invalid Form matrix")
                    self.walk_content(item, item.get("/Resources", resources), page_no, unit,
                                      matrix_mul(matrix, local), depth+1, active | {ident})
                else:
                    self.add("XOBJECT_UNSUPPORTED", "warning", "Nepodporovaný typ grafického objektu.", page_no, {"subtype": subtype})
        if stack:
            self.add("GRAPHICS_STACK_INVALID", "error", "Neuzavretý grafický stav PDF.", page_no)

    def inspect_image(self, image, matrix, page, unit, resources, inline=False):
        width = int(image.get("/Width", image.get("/W", 0)))
        height = int(image.get("/Height", image.get("/H", 0)))
        if not (0 < width <= 100_000 and 0 < height <= 100_000):
            self.add("IMAGE_DIMENSIONS_INVALID", "error", "Neplatné rozmery rastera.", page)
            return
        color = self.color(image.get("/ColorSpace", image.get("/CS", "/DeviceGray")), resources)
        self.colors.add(color)
        try:
            dpi = image_dpi(matrix, width, height, unit)
        except ValueError:
            self.add("IMAGE_TRANSFORM_UNKNOWN", "warning", "Nedá sa spoľahlivo určiť efektívne rozlíšenie obrázka.", page)
            return
        record = {"page": page, "width_px": width, "height_px": height, "effective_dpi": round(dpi, 2), "color_space": color, "inline": inline}
        self.images.append(record)
        if len(self.images) > 5000:
            raise InspectionLimit("Image placement limit")
        if dpi + 0.01 < self.rules.min_dpi:
            self.add("IMAGE_LOW_DPI", "error", "Efektívne rozlíšenie obrázka je nižšie než vyžaduje profil.", page,
                     {"actual_dpi": round(dpi, 1), "required_dpi": self.rules.min_dpi, "width_px": width, "height_px": height})
        if image.get("/SMask") or image.get("/Mask"):
            self.add("IMAGE_MASK_PRESENT", "warning", "Obrázok používa masku; vizuálny výsledok vyžaduje kontrolu.", page)

    def scan_active_objects(self):
        seen = set()
        count = 0
        todo = [(self.reader.trailer, 0)]
        interactive = set()
        while todo:
            item, depth = todo.pop()
            count += 1
            if count > MAX_OBJECTS or depth > 80:
                raise InspectionLimit("PDF object traversal limit")
            if isinstance(item, IndirectObject):
                key = (item.idnum, item.generation)
                if key in seen:
                    continue
                seen.add(key)
                item = obj(item)
            if isinstance(item, DictionaryObject):
                for key, value in item.items():
                    if key in ("/JS", "/JavaScript", "/OpenAction", "/AA", "/Launch", "/RichMedia", "/XFA", "/EmbeddedFiles"):
                        interactive.add(str(key))
                    if key == "/Type" and str(value) == "/EmbeddedFile":
                        interactive.add("/EmbeddedFile")
                    if key == "/S" and str(value) in ("/JavaScript", "/Launch", "/GoToR", "/SubmitForm", "/ImportData"):
                        interactive.add(str(value))
                    if key == "/FT" and str(value) == "/Sig":
                        self.add("SIGNATURE_PRESENT", "warning", "Dokument obsahuje podpisové pole; platnosť podpisu sa neoveruje.")
                    if key == "/AcroForm":
                        self.add("FORM_PRESENT", "warning", "Formulárové polia môžu mať odlišný výsledok tlače; vyžadujú kontrolu.")
                    todo.append((value, depth + 1))
            elif isinstance(item, ArrayObject):
                todo.extend((value, depth + 1) for value in item)
        if interactive:
            self.add("ACTIVE_CONTENT", "error", "PDF obsahuje aktívny obsah, akcie alebo vložené súbory. Automatické prijatie je zablokované.", evidence={"markers": sorted(interactive)})

    def run(self):
        self.reader = PdfReader(io.BytesIO(self.data), strict=True)
        if self.reader.is_encrypted:
            self.add("PDF_ENCRYPTED", "error", "Šifrované PDF sa v MVP nespracúva; vyžiadajte nešifrovaný podklad.")
            return self.result()
        count = len(self.reader.pages)
        if count > 200:
            raise InspectionLimit("Document exceeds 200 pages")
        if not self.rules.min_pages <= count <= self.rules.max_pages:
            self.add("PAGE_COUNT", "error", "Počet strán nezodpovedá výrobnému profilu.", evidence={"actual": count, "min": self.rules.min_pages, "max": self.rules.max_pages})
        self.scan_active_objects()
        for number, page in enumerate(self.reader.pages, 1):
            unit = float(page.get("/UserUnit", 1))
            if not math.isfinite(unit) or not 0 < unit <= 75_000:
                raise ValueError("Invalid UserUnit")
            media = box(page.mediabox)
            crop = box(page.cropbox)
            explicit_trim = "/TrimBox" in page
            trim = box(page.trimbox)
            bleed = box(page.bleedbox)
            rotate = int(page.get("/Rotate", 0)) % 360
            if rotate not in (0, 90, 180, 270):
                self.add("ROTATION_INVALID", "error", "Rotácia strany nie je násobkom 90 stupňov.", number)
            factor = unit * 25.4 / 72
            width, height = (trim[2]-trim[0])*factor, (trim[3]-trim[1])*factor
            if rotate in (90, 270):
                width, height = height, width
            if max(width, height) > 3000:
                self.add("PAGE_TOO_LARGE", "error", "Fyzický rozmer strany prekračuje podporovaných 3 000 mm.", number)
            if not within(trim, media) or not within(bleed, media) or not within(crop, media) or not within(trim, bleed):
                self.add("PAGE_BOXES_INVALID", "error", "TrimBox, BleedBox a MediaBox majú nekonzistentnú geometriu.", number)
            margins = [(trim[0]-bleed[0])*factor, (trim[1]-bleed[1])*factor, (bleed[2]-trim[2])*factor, (bleed[3]-trim[3])*factor]
            self.pages.append({"page": number, "width_mm": round(width, 2), "height_mm": round(height, 2), "rotation": rotate,
                "user_unit": unit, "explicit_trim_box": explicit_trim, "bleed_margins_mm": [round(v, 2) for v in margins]})
            if self.rules.require_explicit_trim and not explicit_trim:
                self.add("TRIM_BOX_MISSING", "error", "Profil vyžaduje explicitne definovaný TrimBox.", number)
            if self.rules.trim_width_mm is not None:
                expected = (self.rules.trim_width_mm, self.rules.trim_height_mm)
                if abs(width-expected[0]) > self.rules.tolerance_mm or abs(height-expected[1]) > self.rules.tolerance_mm:
                    self.add("TRIM_SIZE_MISMATCH", "error", "Čistý formát sa nezhoduje s výrobným profilom.", number,
                             {"actual_mm": [round(width, 2), round(height, 2)], "expected_mm": list(expected)})
            if min(margins) + 0.05 < self.rules.bleed_mm:
                self.add("BLEED_TOO_SMALL", "error", "Geometrická spadávka je menšia než vyžaduje profil.", number,
                         {"margins_mm": [round(n, 2) for n in margins], "required_mm": self.rules.bleed_mm})
            if page.get("/Annots"):
                self.add("ANNOTATIONS_PRESENT", "warning", "Anotácie môžu ovplyvniť tlačový výstup. Skontrolujte ich nastavenia tlače.", number)
            if page.get("/Contents"):
                self.walk_content(page.get("/Contents"), page.get("/Resources", {}), number, unit)
        metadata = self.reader.metadata or {}
        declaration = str(metadata.get("/GTS_PDFXVersion", ""))[:120]
        if declaration:
            self.add("PDFX_DECLARATION_ONLY", "info", "PDF deklaruje PDF/X. Deklarácia nie je dôkazom zhody so štandardom.", evidence={"claim": declaration})
        if self.rules.flag_rgb and any("RGB" in color for color in self.colors):
            self.add("RGB_REVIEW", "warning", "Profil označuje RGB objekty na kontrolu; automatická CMYK konverzia sa nevykonáva.")
        return self.result()

    def result(self):
        counts = Counter(f["severity"] for f in self.findings)
        return {
            "schema_version": 1,
            "engine": {"name": "presspilot-basic", "version": ENGINE_VERSION, "pypdf_version": version("pypdf")},
            "file_sha256": hashlib.sha256(self.data).hexdigest(),
            "profile_digest": digest(self.rules.model_dump()),
            "status": "blocked" if counts["error"] else "review",
            "print_ready": False,
            "release_allowed": False,
            "coverage": COVERAGE,
            "summary": {"pages": len(self.pages), "errors": counts["error"], "warnings": counts["warning"], "info": counts["info"],
                        "image_placements": len(self.images), "fonts": len(self.fonts), "color_spaces": sorted(self.colors)},
            "pages": self.pages, "images": self.images, "fonts": self.fonts, "findings": self.findings,
        }


def inspect_pdf(data: bytes, rules: dict) -> dict:
    inspector = Inspector(data, rules)
    try:
        return inspector.run()
    except InspectionLimit as exc:
        # Never return a partial successful report after a resource/coverage limit.
        return {"schema_version": 1, "status": "error", "error_code": "INSPECTION_LIMIT", "detail": str(exc),
                "print_ready": False, "release_allowed": False, "file_sha256": hashlib.sha256(data).hexdigest()}
    except Exception:
        return {"schema_version": 1, "status": "error", "error_code": "PDF_PARSE_FAILED",
                "print_ready": False, "release_allowed": False, "file_sha256": hashlib.sha256(data).hexdigest()}
