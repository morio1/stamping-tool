"""Create fictitious certificates and a TEST ONLY stamp for trying the application."""
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont


def main():
    root = Path(__file__).resolve().parent / "output" / "demo"
    root.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (600, 240), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((5, 5, 595, 235), radius=20, outline="#164ba0", width=10)
    font = ImageFont.truetype("arial.ttf", 52) if Path("C:/Windows/Fonts/arial.ttf").exists() else ImageFont.load_default(size=48)
    draw.text((300, 75), "SAMPLE COLLEGE", fill="#164ba0", font=font, anchor="mm")
    draw.text((300, 160), "TEST ONLY", fill="#164ba0", font=font, anchor="mm")
    image.save(root / "test-stamp.png")
    signature = Image.new("RGBA", (600, 150), (255, 255, 255, 0))
    pen = ImageDraw.Draw(signature)
    pen.line([(35, 95), (90, 25), (65, 100), (145, 48), (130, 95),
              (200, 55), (225, 88), (300, 55), (340, 85), (465, 45), (540, 65)],
             fill="#164ba0", width=5)
    pen.text((300, 125), "SAMPLE ONLY", fill="#164ba0", font=ImageFont.load_default(size=22), anchor="mm")
    signature.save(root / "sample-signature.png")
    for region, y, rotated in [("Nairobi", 420, False), ("Mombasa", 500, True)]:
        folder = root / "certificates" / region
        folder.mkdir(parents=True, exist_ok=True)
        with fitz.open() as doc:
            for n in range(2):
                page = doc.new_page(width=595, height=842)
                page.insert_text((70, 80), "SAMPLE CERTIFICATE", fontsize=26, color=(0.06, 0.16, 0.26))
                page.insert_text((70, 115), "FICTITIOUS DATA - FOR SOFTWARE TESTING ONLY", fontsize=10)
                page.insert_text((70, 180), f"Regional centre: {region}", fontsize=14)
                page.insert_text((70, 210), f"Candidate: Example Student {n + 1}", fontsize=14)
                page.insert_text((147, y + n * 30), "College Stamp & Date:", fontsize=11)
                page.draw_rect(fitz.Rect(147, y + n * 30 + 10, 347, y + n * 30 + 100), color=(0.3, 0.4, 0.5))
                page.draw_line((147, 670), (347, 670), color=(0.3, 0.4, 0.5))
                page.insert_text((210, 690), "Principal", fontsize=11)
                if rotated:
                    page.set_rotation(90)
            doc.save(folder / "sample.pdf")
    print(f"Demo input: {root / 'certificates'}")
    print(f"Test stamp: {root / 'test-stamp.png'}")
    print(f"Sample signature: {root / 'sample-signature.png'}")


if __name__ == "__main__":
    main()
