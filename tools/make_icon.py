"""Draws ABBA's icon and the window's header logo: the red square, AB over BA.

    uv run --no-project --with pillow python tools/make_icon.py

Drawn rather than scaled down from a bitmap: each size is rendered large and
reduced on its own, so that the letters stay sharp at 16 px. Writes into the
package's assets/:

    app.ico             the shortcuts' icon, every size Windows asks for
    icon-<n>.png        the window and taskbar icon
    logo-<scale>.png    the window's header logo, per display scale (Tk cannot
                        resize an image smoothly)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "src" / "abba_installer" / "assets"
RED = (227, 6, 19)  # the red of ABBA's logo
WHITE = (255, 255, 255)
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
PNG_SIZES = (16, 32, 48, 256)
#: The header logo is 56 px tall at 100 %.
LOGO_PX = 56
LOGO_SCALES = (100, 125, 150, 175, 200, 250, 300)
FONTS = ("C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf")
BIG = 1024


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    raise SystemExit("no bold sans-serif font found; add one to FONTS")


def draw(size: int) -> Image.Image:
    """The logo at `size` px, drawn at 1024 px and reduced."""
    image = Image.new("RGBA", (BIG, BIG), RED)
    canvas = ImageDraw.Draw(image)
    letters = font(int(BIG * 0.40))
    cell = BIG / 2
    for row, word in enumerate(("AB", "BA")):
        for column, letter in enumerate(word):
            # Centred on the letter's own ink, not on the font's line box.
            left, top, right, bottom = canvas.textbbox((0, 0), letter, font=letters)
            x = column * cell + (cell - (right - left)) / 2 - left
            y = row * cell + (cell - (bottom - top)) / 2 - top
            canvas.text((x, y), letter, font=letters, fill=WHITE)
    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    largest = draw(256)
    largest.save(ASSETS / "app.ico", sizes=[(s, s) for s in ICO_SIZES],
                 append_images=[draw(s) for s in ICO_SIZES if s != 256])
    for size in PNG_SIZES:
        draw(size).save(ASSETS / f"icon-{size}.png")
    for scale in LOGO_SCALES:
        draw(round(LOGO_PX * scale / 100)).save(ASSETS / f"logo-{scale}.png")
    print(f"written to {ASSETS}")


if __name__ == "__main__":
    main()
