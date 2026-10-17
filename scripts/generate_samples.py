"""Generate synthetic PDF fixtures. No customer files or standalone fonts are included."""
from pathlib import Path
import io
import zlib
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter, PdfReader
from pypdf.generic import NameObject, NumberObject, FloatObject, DictionaryObject, DecodedStreamObject, RectangleObject

ROOT = Path(__file__).resolve().parents[1]
MM = 72 / 25.4


def font(size):
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def artwork(width=1200, height=804):
    image = Image.new("RGB", (width, height), "#eee9df")
    draw = ImageDraw.Draw(image)
    scale = width / 1200
    def rectangle(bounds, fill):
        draw.rectangle(tuple(int(n*scale) for n in bounds), fill=fill)
    rectangle((0, 0, 55, 804), "#b7da5c")
    rectangle((0, 595, 1200, 804), "#193f36")
    draw.text((int(130*scale), int(112*scale)), "NORTH", font=font(max(10, int(142*scale))), fill="#193f36")
    draw.text((int(139*scale), int(294*scale)), "DESIGN STUDIO", font=font(max(8, int(40*scale))), fill="#193f36")
    draw.text((int(139*scale), int(402*scale)), "Good ideas. Beautifully printed.", font=font(max(7, int(28*scale))), fill="#60655d")
    draw.text((int(139*scale), int(659*scale)), "SYNTHETIC PRESSPILOT TEST FILE", font=font(max(7, int(25*scale))), fill="#f3f3df")
    return image.convert("CMYK")


def card(path, bleed=True, pixels=1200, unembedded=False, active=False, claim=False):
    writer = PdfWriter()
    width_mm, height_mm = (91, 61) if bleed else (85, 55)
    page = writer.add_blank_page(width=width_mm*MM, height=height_mm*MM)
    inset = 3*MM if bleed else 0
    page.trimbox = RectangleObject([inset, inset, width_mm*MM-inset, height_mm*MM-inset])
    page.bleedbox = RectangleObject([0, 0, width_mm*MM, height_mm*MM])
    picture = artwork(pixels, round(pixels*height_mm/width_mm))
    stream = DecodedStreamObject()
    stream.set_data(picture.tobytes())
    stream.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Image"),
                   NameObject("/Width"): NumberObject(picture.width), NameObject("/Height"): NumberObject(picture.height),
                   NameObject("/ColorSpace"): NameObject("/DeviceCMYK"), NameObject("/BitsPerComponent"): NumberObject(8)})
    image_ref = writer._add_object(stream.flate_encode())
    resources = DictionaryObject({NameObject("/XObject"): DictionaryObject({NameObject("/Im0"): image_ref})})
    commands = f"q {width_mm*MM} 0 0 {height_mm*MM} 0 0 cm /Im0 Do Q\n"
    if unembedded:
        resources[NameObject("/Font")] = DictionaryObject({NameObject("/F1"): writer._add_object(DictionaryObject({
            NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")}))})
        commands += "BT /F1 8 Tf 10 10 Td (Unembedded font fixture) Tj ET\n"
    page[NameObject("/Resources")] = resources
    contents = DecodedStreamObject()
    contents.set_data(commands.encode())
    page[NameObject("/Contents")] = writer._add_object(contents)
    if active:
        writer.add_js("app.alert('Synthetic PressPilot test - benign action');")
    if claim:
        writer.add_metadata({"/GTS_PDFXVersion": "PDF/X-4"})
    writer.add_metadata({"/Title": "Synthetic PressPilot test fixture", "/Producer": "PressPilot fixture generator"})
    writer.write(path)


def main():
    samples = ROOT / "samples"
    samples.mkdir(exist_ok=True)
    card(samples / "01-vizitka-kontrola.pdf")
    card(samples / "02-chybajuca-spadavka.pdf", bleed=False)
    card(samples / "03-nizke-rozlisenie.pdf", pixels=120)
    card(samples / "04-nevlozeny-font.pdf", unembedded=True)
    card(samples / "05-aktivny-obsah.pdf", active=True)
    (samples / "06-poskodeny-subor.pdf").write_bytes(b"%PDF-1.7\nThis is intentionally malformed synthetic input.\n")
    reader = PdfReader(samples / "01-vizitka-kontrola.pdf")
    writer = PdfWriter()
    writer.append(reader)
    writer.encrypt("sample-only", algorithm="AES-256")
    writer.write(samples / "07-sifrovany.pdf")
    card(samples / "08-deklaracia-pdfx.pdf", claim=True)
    print(f"Created 8 synthetic fixtures in {samples}")


if __name__ == "__main__":
    main()
