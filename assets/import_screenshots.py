"""
import_screenshots.py
----------------------
Resizes your own CS2 screenshots to the right dimensions for Discord Rich
Presence and writes them into `assets/maps/`.

Why does this script exist?
    We can't ship Valve's copyrighted in-game images ready-made in this
    repo (permanently copying someone else's copyrighted image into a git
    repository under your name wouldn't be right). But using screenshots
    YOU took yourself is entirely your choice and your right — this
    script just makes that easier.

Usage:
    1) Join a match in CS2, take a screenshot with F12 (Steam screenshot)
       or any other method you like.
    2) Save the file under one of these names into
       `assets/screenshots_raw/` (extension can be .jpg/.jpeg/.png):

           de_dust2, de_mirage, de_inferno, de_nuke, de_overpass,
           de_vertigo, de_ancient, de_anubis, de_train, de_cache,
           cs_office, cs_italy, cs_agency, de_shortdust, de_lake,
           de_stmarc, de_grail, aim_map, cs2_logo

       example: assets/screenshots_raw/de_mirage.jpg

    3) pip install -r requirements.txt   (Pillow)
    4) python import_screenshots.py

    The script center-crops each image to 1024x576 (16:9) and saves it as
    `assets/maps/<map>.png` — cs2_discord_rpc.py uses these files
    automatically, no code changes needed.
"""

from __future__ import annotations

import os

from PIL import Image, ImageOps

RAW_DIR = os.path.join(os.path.dirname(__file__), "screenshots_raw")
OUT_DIR = os.path.join(os.path.dirname(__file__), "maps")
TARGET_SIZE = (1024, 576)  # 16:9 - works well for map screenshots
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# cs2_logo is always used as the large image on Discord and is usually a
# square/symmetric logo - forcibly cropping it to 16:9 (especially a
# square logo) could cut off critical parts. So we use a separate, square
# target size for the logo.
SPECIAL_TARGET_SIZES = {
    "cs2_logo": (512, 512),
}


def process_one(src_path: str, out_path: str, target_size: tuple[int, int]) -> None:
    img = Image.open(src_path).convert("RGB")
    # ImageOps.fit: center-crops and resizes to the target aspect ratio
    # without distorting the image (no stretching).
    fitted = ImageOps.fit(img, target_size, method=Image.LANCZOS)
    fitted.save(out_path, "PNG")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    if not os.path.isdir(RAW_DIR):
        os.makedirs(RAW_DIR, exist_ok=True)
        print(
            f"Created the '{RAW_DIR}' folder.\n"
            "Put your screenshots in this folder (e.g. de_mirage.jpg) and "
            "run the script again."
        )
        return

    processed = 0
    for filename in sorted(os.listdir(RAW_DIR)):
        name, ext = os.path.splitext(filename)
        if ext.lower() not in VALID_EXTENSIONS:
            continue
        src = os.path.join(RAW_DIR, filename)
        out = os.path.join(OUT_DIR, f"{name}.png")
        target_size = SPECIAL_TARGET_SIZES.get(name, TARGET_SIZE)
        process_one(src, out, target_size)
        print(f"processed: {filename} -> {out} ({target_size[0]}x{target_size[1]})")
        processed += 1

    if processed == 0:
        print(
            f"No images found to process in '{RAW_DIR}' "
            f"({', '.join(VALID_EXTENSIONS)})."
        )
    else:
        print(f"\nUpdated {processed} image(s) in total.")


if __name__ == "__main__":
    main()
