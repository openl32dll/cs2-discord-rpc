"""
generate_map_icons.py
----------------------
`cs2-discord-rpc/assets/maps/` klasöründeki küçük harita ikonlarını üretir.

Bu görseller Valve'ın telifli oyun içi ekran görüntüleri DEĞİLDİR; bu repo
için sıfırdan çizilmiş basit, tek renkli "rozet" tarzı ikonlardır (harita
adı + küçük bir nişangah simgesi). Amaç, Discord Rich Presence'ta her
haritayı görsel olarak ayırt edilebilir kılmak; Discord Developer Portal'a
manuel görsel yüklemeye gerek kalmadan `cs2_discord_rpc.py`, bu PNG'lerin
GitHub üzerindeki ham (raw) URL'sini doğrudan Discord'a "external image
URL" olarak veriyor.

Yeniden üretmek / yeni harita eklemek istersen:
    pip install Pillow
    python generate_map_icons.py
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "maps")
SIZE = 512
FONT_PATH_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

# harita_kodu -> (Görünen kısa etiket, arkaplan rengi (RGB), yazı rengi)
MAPS = {
    "de_dust2":     ("DUST II", (196, 154, 91)),
    "de_mirage":    ("MIRAGE", (214, 168, 92)),
    "de_inferno":   ("INFERNO", (176, 82, 55)),
    "de_nuke":      ("NUKE", (92, 156, 158)),
    "de_overpass":  ("OVERPASS", (86, 133, 90)),
    "de_vertigo":   ("VERTIGO", (110, 118, 140)),
    "de_ancient":   ("ANCIENT", (95, 128, 97)),
    "de_anubis":    ("ANUBIS", (200, 176, 120)),
    "de_train":     ("TRAIN", (120, 120, 128)),
    "de_cache":     ("CACHE", (146, 158, 104)),
    "cs_office":    ("OFFICE", (108, 96, 140)),
    "cs_italy":     ("ITALY", (188, 140, 96)),
    "cs_agency":    ("AGENCY", (90, 108, 150)),
    "de_shortdust": ("SHORT DUST", (196, 154, 91)),
    "de_lake":      ("LAKE", (78, 128, 150)),
    "de_stmarc":    ("ST. MARC", (150, 120, 96)),
    "de_grail":     ("GRAIL", (150, 96, 110)),
    "aim_map":      ("AIM MAP", (120, 120, 120)),
}

# Genel / bilinmeyen harita ve ana menü için varsayılan logo.
FALLBACK = ("cs2_logo", "CS2", (60, 60, 66))


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_PATH_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_crosshair(draw: ImageDraw.ImageDraw, cx: int, cy: int, color) -> None:
    gap, length, thickness = 14, 46, 10
    draw.line((cx - gap - length, cy, cx - gap, cy), fill=color, width=thickness)
    draw.line((cx + gap, cy, cx + gap + length, cy), fill=color, width=thickness)
    draw.line((cx, cy - gap - length, cx, cy - gap), fill=color, width=thickness)
    draw.line((cx, cy + gap, cx, cy + gap + length), fill=color, width=thickness)
    draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=color)


def _make_icon(label: str, bg_color) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), bg_color)
    draw = ImageDraw.Draw(img)

    # Hafif koyu kenarlık.
    border = 10
    draw.rectangle(
        (border // 2, border // 2, SIZE - border // 2, SIZE - border // 2),
        outline=(0, 0, 0),
        width=border,
    )

    text_color = (255, 255, 255)
    _draw_crosshair(draw, SIZE // 2, 175, text_color)

    # Harita adını sığdırana kadar font boyutunu küçült.
    font_size = 68
    font = _load_font(font_size)
    max_width = SIZE - 80
    while font.getlength(label) > max_width and font_size > 24:
        font_size -= 4
        font = _load_font(font_size)

    text_w = font.getlength(label)
    text_h = font_size
    draw.text(
        ((SIZE - text_w) / 2, 300 - text_h / 2),
        label,
        font=font,
        fill=text_color,
    )

    small_font = _load_font(30)
    tag = "COUNTER-STRIKE 2"
    tag_w = small_font.getlength(tag)
    draw.text(((SIZE - tag_w) / 2, SIZE - 70), tag, font=small_font, fill=(255, 255, 255))

    return img


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    for map_key, (label, color) in MAPS.items():
        icon = _make_icon(label, color)
        out_path = os.path.join(OUT_DIR, f"{map_key}.png")
        icon.save(out_path)
        print(f"yazıldı: {out_path}")

    fallback_key, fallback_label, fallback_color = FALLBACK
    icon = _make_icon(fallback_label, fallback_color)
    out_path = os.path.join(OUT_DIR, f"{fallback_key}.png")
    icon.save(out_path)
    print(f"yazıldı: {out_path}")


if __name__ == "__main__":
    main()
