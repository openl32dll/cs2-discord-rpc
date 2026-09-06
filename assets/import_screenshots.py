"""
import_screenshots.py
----------------------
Kendi aldığın CS2 ekran görüntülerini Discord Rich Presence için uygun
boyuta getirip `assets/maps/` klasörüne yazar.

Neden bu script var?
    Valve'ın telifli oyun içi görsellerini bu repoya hazır olarak
    koyamıyoruz (hem bu bilgisayarın internete kısıtlı erişimi var hem de
    başkasının telifli görselini senin adına bir git deposuna kalıcı
    olarak kopyalamak doğru olmaz). Ama SENİN kendi aldığın ekran
    görüntülerini kullanman tamamen senin tercihin ve hakkın - bu script
    de bunu kolaylaştırıyor.

Kullanım:
    1) CS2 içinde bir maça gir, F12 (Steam screenshot) ya da istediğin
       başka bir yöntemle ekran görüntüsü al.
    2) Dosyayı şu isimlerden biriyle `assets/screenshots_raw/` klasörüne
       koy (uzantı .jpg/.jpeg/.png olabilir):

           de_dust2, de_mirage, de_inferno, de_nuke, de_overpass,
           de_vertigo, de_ancient, de_anubis, de_train, de_cache,
           cs_office, cs_italy, cs_agency, de_shortdust, de_lake,
           de_stmarc, de_grail, aim_map, cs2_logo

       örnek: assets/screenshots_raw/de_mirage.jpg

    3) pip install -r requirements.txt   (Pillow)
    4) python import_screenshots.py

    Script, her görüntüyü 1024x576 (16:9) boyutuna ortalayarak kırpıp
    `assets/maps/<harita>.png` olarak kaydeder — cs2_discord_rpc.py bu
    dosyaları otomatik kullanır, kod tarafında hiçbir değişiklik gerekmez.
"""

from __future__ import annotations

import os

from PIL import Image, ImageOps

RAW_DIR = os.path.join(os.path.dirname(__file__), "screenshots_raw")
OUT_DIR = os.path.join(os.path.dirname(__file__), "maps")
TARGET_SIZE = (1024, 576)  # 16:9 - harita ekran görüntüleri için iyi çalışan oran
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# cs2_logo, Discord'da her zaman büyük görsel olarak kullanılıyor ve
# genelde kare/simetrik bir logo oluyor - onu 16:9'a zorla kırpmak
# (özellikle kare bir logoyu) kafa/ayak gibi kritik kısımları kesip
# atabilir. Bu yüzden logo için ayrı, kare bir hedef boyut kullanıyoruz.
SPECIAL_TARGET_SIZES = {
    "cs2_logo": (512, 512),
}


def process_one(src_path: str, out_path: str, target_size: tuple[int, int]) -> None:
    img = Image.open(src_path).convert("RGB")
    # ImageOps.fit: hedef orana göre ortadan kırpıp yeniden boyutlandırır,
    # görüntü bozulmaz (stretch yapmaz).
    fitted = ImageOps.fit(img, target_size, method=Image.LANCZOS)
    fitted.save(out_path, "PNG")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    if not os.path.isdir(RAW_DIR):
        os.makedirs(RAW_DIR, exist_ok=True)
        print(
            f"'{RAW_DIR}' klasörünü oluşturdum.\n"
            "Ekran görüntülerini bu klasöre (ör. de_mirage.jpg) koyup "
            "scripti tekrar çalıştır."
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
        print(f"işlendi: {filename} -> {out} ({target_size[0]}x{target_size[1]})")
        processed += 1

    if processed == 0:
        print(
            f"'{RAW_DIR}' klasöründe işlenecek görsel bulunamadı "
            f"({', '.join(VALID_EXTENSIONS)})."
        )
    else:
        print(f"\nToplam {processed} görsel güncellendi.")


if __name__ == "__main__":
    main()
