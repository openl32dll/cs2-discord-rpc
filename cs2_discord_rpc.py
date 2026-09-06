"""
cs2_discord_rpc.py
------------------
Counter-Strike 2 oynarken Discord'da özel bir "Rich Presence" (oyun durumu)
gösterir: hangi haritada olduğun, kaçıncı roundda olduğun ve hangi oyun
modunda olduğun (Rekabetçi / Premier, Yoldaş (Wingman), Basit (Casual),
Deathmatch, Silah Yarışı, Yıkım, vb.).

Nasıl çalışır?
    1) CS2, Valve'ın "Game State Integration" (GSI) özelliği sayesinde
       oyun içi durumu bir HTTP isteğiyle yerel bilgisayarına gönderebilir.
       Bunun için `gamestate_integration_discordrpc.cfg` dosyasını CS2'nin
       config klasörüne kopyalaman gerekiyor (bkz. README.md).
    2) Bu script, o isteği karşılamak için yerelde küçük bir HTTP sunucusu
       açar (varsayılan: http://127.0.0.1:3000).
    3) Gelen veriyi (harita, mod, round, skor, bomba durumu vb.) okuyup
       `pypresence` kütüphanesiyle Discord masaüstü uygulamasına iletir.

Kurulum:
    pip install -r requirements.txt

Kullanım:
    DISCORD_CLIENT_ID=xxxxxxxxxxxxxxxxxx python cs2_discord_rpc.py

    Alternatif (özellikle Windows başlangıcına eklerken pratik):
    `config.example.json` dosyasını `config.json` olarak kopyala, içine
    Client ID'ni yaz; script ortam değişkeni yerine bu dosyayı okur.
    Windows'ta oturum açılışında otomatik başlatmak için
    windows_autostart/install_autostart.ps1 kullanılabilir.

Discord Client ID nasıl alınır, GSI dosyası nereye konur -> README.md
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

try:
    from pypresence import Presence
    from pypresence.exceptions import DiscordNotFound, PipeClosed
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "pypresence kütüphanesi bulunamadı. Kurmak için:\n"
        "    pip install -r requirements.txt"
    ) from exc


# --------------------------------------------------------------------------
# Ayarlar
# --------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cs2-discord-rpc")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
PLACEHOLDER_CLIENT_ID = "PUT_YOUR_DISCORD_CLIENT_ID_HERE"


def _read_config_file() -> dict:
    """`config.json` içeriğini okur (yoksa/bozuksa boş sözlük döner)."""
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("config.json okunamadı, varsayılanlara geri dönülüyor: %s", exc)
        return {}


_CONFIG = _read_config_file()


def _setting(env_var: str, config_key: str, default: Optional[str]) -> Optional[str]:
    """Bir ayarı önce ortam değişkeninden, yoksa config.json'dan, o da
    yoksa verilen varsayılan değerden okur.

    config.json kullanmak, özellikle Windows başlangıcına (Görev
    Zamanlayıcı) eklerken işine yarar: ortam değişkeni her oturumda
    yeniden ayarlanmak zorunda kalmadan, ayarı bir kere dosyaya yazman
    yeterli olur (bkz. windows_autostart/ ve README.md).
    """
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value
    config_value = _CONFIG.get(config_key)
    if config_value:
        return str(config_value)
    return default


def load_client_id() -> str:
    return _setting("DISCORD_CLIENT_ID", "discord_client_id", PLACEHOLDER_CLIENT_ID)


# Discord Developer Portal'da oluşturduğun uygulamanın Client ID'si.
# https://discord.com/developers/applications -> New Application -> General
# Ortam değişkeni (DISCORD_CLIENT_ID) veya config.json ile ayarlanabilir.
DISCORD_CLIENT_ID = load_client_id()

# CS2'nin GSI verisini göndereceği yerel adres/port.
# gamestate_integration_discordrpc.cfg dosyasındaki "uri" ile eşleşmeli.
GSI_HOST = "127.0.0.1"
GSI_PORT = 3000

# Aynı durum değişmediği sürece Discord'a en fazla bu sıklıkta güncelleme
# gönderilir (Discord IPC'yi gereksiz yere yormamak için).
MIN_UPDATE_INTERVAL_SECONDS = 4.0

# Oyuncudan hiç veri gelmezse bu süre sonunda durum temizlenir
# (oyun kapatıldı / CS2'den çıkıldı olarak yorumlanır).
STALE_TIMEOUT_SECONDS = 20.0


# --------------------------------------------------------------------------
# CS2 oyun modları
#
# CS2'nin GSI çıktısındaki "map.mode" alanı, oyuncunun içinde bulunduğu
# oyun moduna göre değişir. Aşağıdaki tablo, bilinen tüm mod anahtarlarını
# görünen isimlere ve moda özgü davranışlara (round sayılıp sayılmayacağı,
# varsayılan maksimum round) eşler.
#
# Not: "max_rounds" değerleri CS2'nin standart matchmaking ayarlarına göre
# varsayılan değerlerdir (ör. Rekabetçi/Premier MR12 -> 24 round, Yoldaş
# MR8 -> 16 round). Özel sunucularda (custom/community server) bu limitler
# farklı olabilir; bilinmiyorsa sadece geçerli round gösterilir.
# --------------------------------------------------------------------------

@dataclass
class ModeInfo:
    label: str          # Discord'da gösterilecek Türkçe mod adı
    has_rounds: bool     # Bu modda "round" kavramı var mı?
    max_rounds: Optional[int] = None  # Varsayılan maksimum round (varsa)


MODE_INFO: dict[str, ModeInfo] = {
    # Rekabetçi / Premier (ikisi de GSI'da "competitive" olarak gelebilir)
    "competitive":        ModeInfo("Rekabetçi", True, 24),
    "scrimcomp5v5":       ModeInfo("Premier", True, 24),
    # Yoldaş (Wingman) 2v2
    "scrimcomp2v2":       ModeInfo("Yoldaş (Wingman)", True, 16),
    # Basit / Gündelik
    "casual":             ModeInfo("Basit", True, None),
    # Deathmatch: round yok, sürekli respawn + skor tablosu var
    "deathmatch":         ModeInfo("Deathmatch", False),
    # Silah Yarışı (Arms Race)
    "gungameprogressive": ModeInfo("Silah Yarışı", False),
    # Yıkım (Demolition)
    "gungametrbomb":      ModeInfo("Yıkım", True, None),
    # Uçan Keşif Nişancısı / diğer "skirmish" tipi modlar
    "skirmish":           ModeInfo("Uçan Keşif Nişancısı", True, None),
    # Co-op Strike / Guardian gibi işbirlikçi modlar
    "cooperative":        ModeInfo("Ko-op Görev", False),
    # Antrenman
    "training":           ModeInfo("Antrenman", False),
    # Özel oyun / community sunucular
    "custom":             ModeInfo("Özel Oyun", True, None),
    # Tehlike Bölgesi (battle royale, eski CS:GO modu)
    "survival":           ModeInfo("Tehlike Bölgesi", False),
}

DEFAULT_MODE = ModeInfo("Bilinmeyen Mod", True, None)


def mode_info_for(mode_key: Optional[str]) -> ModeInfo:
    if not mode_key:
        return DEFAULT_MODE
    return MODE_INFO.get(mode_key, DEFAULT_MODE)


# --------------------------------------------------------------------------
# Harita isimleri
#
# GSI, harita adını "de_dust2" gibi teknik kodlarla gönderir. Bunları daha
# okunaklı isimlere çeviriyoruz; listede olmayan bir harita gelirse ön eki
# atıp baş harfleri büyültülmüş haliyle gösteriyoruz (ör. "de_newmap" ->
# "Newmap").
# --------------------------------------------------------------------------

MAP_DISPLAY_NAMES = {
    "de_dust2": "Dust II",
    "de_mirage": "Mirage",
    "de_inferno": "Inferno",
    "de_nuke": "Nuke",
    "de_overpass": "Overpass",
    "de_vertigo": "Vertigo",
    "de_ancient": "Ancient",
    "de_anubis": "Anubis",
    "de_train": "Train",
    "de_cache": "Cache",
    "cs_office": "Office",
    "cs_italy": "Italy",
    "cs_agency": "Agency",
    "de_shortdust": "Short Dust (Wingman)",
    "de_lake": "Lake (Wingman)",
    "de_stmarc": "St. Marc (Wingman)",
    "de_grail": "Grail (Wingman)",
    "aim_map": "Aim Map",
}


def display_map_name(raw_name: Optional[str]) -> str:
    if not raw_name:
        return "Bilinmeyen Harita"
    if raw_name in MAP_DISPLAY_NAMES:
        return MAP_DISPLAY_NAMES[raw_name]
    # "de_", "cs_", "aim_" gibi ön ekleri temizleyip düzgün göster.
    for prefix in ("de_", "cs_", "aim_", "gd_", "ar_"):
        if raw_name.startswith(prefix):
            return raw_name[len(prefix):].replace("_", " ").title()
    return raw_name.replace("_", " ").title()


# --------------------------------------------------------------------------
# Harita görselleri
#
# Discord Developer Portal'daki uygulamanın "Rich Presence -> Art Assets"
# kısmına yüklediğin görsellerin ANAHTAR (key) isimlerini kullanıyoruz
# (dış URL değil). Bu, klasik masaüstü Rich Presence (yerel IPC) ile en
# garantili çalışan yöntem. Her harita için aşağıdaki isimlerle bir asset
# yükle (uzantısız, hepsi küçük harf):
#
#   cs2_logo, de_dust2, de_mirage, de_inferno, de_nuke, de_overpass,
#   de_vertigo, de_ancient, de_anubis, de_train, de_cache, cs_office,
#   cs_italy, cs_agency, de_shortdust, de_lake, de_stmarc, de_grail, aim_map
#
# (Görsellerin kendisi bu repoda cs2-discord-rpc/assets/maps/ altında
# hazır duruyor, oradan indirip Developer Portal'a yükleyebilirsin.)
# --------------------------------------------------------------------------

FALLBACK_MAP_IMAGE_KEY = "cs2_logo"


def map_image_key(raw_name: Optional[str]) -> str:
    """GSI'dan gelen harita koduna karşılık gelen Art Asset anahtarını üretir.

    Elimizde hazır görseli olmayan bir harita gelirse (yeni eklenen bir
    harita, community server haritası vb.) genel CS2 logosuna düşer.
    """
    return raw_name if raw_name in MAP_DISPLAY_NAMES else FALLBACK_MAP_IMAGE_KEY


# Discord Rich Presence'ta iki görsel alanı var: büyük ana görsel
# (large_image) ve onun sağ alt köşesinde duran küçük rozet (small_image).
# Burada büyük görsel her zaman sabit CS2 logosu, küçük rozet ise o an
# içinde bulunduğun haritayı gösteriyor.
CS2_LOGO_IMAGE_KEY = FALLBACK_MAP_IMAGE_KEY


# --------------------------------------------------------------------------
# Paylaşılan durum: GSI sunucusu bu nesneyi günceller, sunum (presence)
# döngüsü de buradan okuyarak Discord'a gönderir.
# --------------------------------------------------------------------------

@dataclass
class SharedState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    payload: Optional[dict] = None
    last_seen: float = 0.0

    def update(self, payload: dict) -> None:
        with self.lock:
            self.payload = payload
            self.last_seen = time.monotonic()

    def snapshot(self) -> tuple[Optional[dict], float]:
        with self.lock:
            return self.payload, self.last_seen


state = SharedState()


# --------------------------------------------------------------------------
# GSI HTTP sunucusu: CS2'den gelen POST isteklerini karşılar.
# --------------------------------------------------------------------------

class GSIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - BaseHTTPRequestHandler API
        # Varsayılan gürültülü erişim loglarını sustur.
        pass

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length else b""
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except (ValueError, json.JSONDecodeError) as exc:
            log.warning("Geçersiz GSI verisi alındı: %s", exc)
            self.send_response(400)
            self.end_headers()
            return

        state.update(payload)
        self.send_response(200)
        self.end_headers()


def run_gsi_server() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((GSI_HOST, GSI_PORT), GSIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("GSI sunucusu dinliyor: http://%s:%d", GSI_HOST, GSI_PORT)
    return server


# --------------------------------------------------------------------------
# GSI verisinden Discord'a gösterilecek "details" / "state" metinlerini
# üreten mantık.
# --------------------------------------------------------------------------

def build_presence_fields(payload: dict) -> Optional[dict]:
    """GSI payload'ından Discord Rich Presence alanlarını üretir.

    Oyuncu ana menüdeyse ya da veri eksikse None döner (bu durumda
    presence temizlenir).
    """
    player = payload.get("player") or {}
    map_info = payload.get("map") or {}
    round_info = payload.get("round") or {}

    activity = player.get("activity")
    if activity is not None and activity != "playing":
        # Ana menüde / metin girişinde -> henüz bir harita yok, sadece
        # büyük CS2 logosu gösterilir (küçük harita rozeti olmadan).
        return {
            "details": "Ana menüde geziniyor",
            "state": "Counter-Strike 2",
            "large_image": CS2_LOGO_IMAGE_KEY,
            "large_text": "Counter-Strike 2",
        }

    map_name_raw = map_info.get("name")
    mode_key = map_info.get("mode")
    mode = mode_info_for(mode_key)
    map_name = display_map_name(map_name_raw)

    phase = map_info.get("phase")  # warmup / live / intermission / gameover
    if phase == "warmup":
        details = f"🗺️ {map_name} · {mode.label}"
        state_text = "Isınma turu"
    elif phase == "gameover":
        details = f"🗺️ {map_name} · {mode.label}"
        state_text = "Maç bitti"
    else:
        team_ct = map_info.get("team_ct") or {}
        team_t = map_info.get("team_t") or {}
        ct_score = team_ct.get("score", 0)
        t_score = team_t.get("score", 0)

        details = f"🗺️ {map_name} · {mode.label}"

        if mode.has_rounds:
            current_round = map_info.get("round")
            # GSI round bilgisi 0'dan başlar; insan tarafı için +1.
            round_display = (current_round + 1) if isinstance(current_round, int) else None
            round_text = f"Round {round_display}" if round_display else "Round -"
            if mode.max_rounds:
                round_text += f"/{mode.max_rounds}"
            state_text = f"{round_text} · CT {ct_score} - {t_score} T"
        else:
            # Round kavramı olmayan modlar (Deathmatch, Silah Yarışı, vb.):
            # round yerine kişisel skor/kill bilgisini gösteriyoruz.
            match_stats = player.get("match_stats") or {}
            kills = match_stats.get("kills", 0)
            deaths = match_stats.get("deaths", 0)
            state_text = f"{kills} frag / {deaths} ölüm"

        if round_info.get("bomb") == "planted":
            state_text += " · 💣 Bomba döşendi"

    return {
        "details": details,
        "state": state_text,
        "large_image": CS2_LOGO_IMAGE_KEY,
        "large_text": "Counter-Strike 2",
        "small_image": map_image_key(map_name_raw),
        "small_text": map_name,
    }


def state_key(fields: Optional[dict]) -> tuple:
    if fields is None:
        return ()
    return (
        fields.get("details"),
        fields.get("state"),
        fields.get("large_image"),
        fields.get("small_image"),
    )


# --------------------------------------------------------------------------
# Ana döngü: Discord IPC bağlantısını kurar/canlı tutar ve GSI durumundaki
# değişiklikleri Discord'a yansıtır.
# --------------------------------------------------------------------------

def connect_discord() -> Presence:
    if DISCORD_CLIENT_ID == "PUT_YOUR_DISCORD_CLIENT_ID_HERE":
        raise SystemExit(
            "DISCORD_CLIENT_ID ayarlanmamış. README.md içindeki adımları izleyerek\n"
            "kendi Discord uygulamanı oluştur ve Client ID'sini bu script'e ver\n"
            "(ortam değişkeni: DISCORD_CLIENT_ID)."
        )
    rpc = Presence(DISCORD_CLIENT_ID)
    rpc.connect()
    log.info("Discord'a bağlanıldı (client_id=%s).", DISCORD_CLIENT_ID)
    return rpc


def main() -> None:
    run_gsi_server()

    rpc: Optional[Presence] = None
    last_sent_key: tuple = ("__init__",)
    last_sent_time = 0.0
    cleared_for_stale = True
    start_time = time.time()

    while True:
        try:
            if rpc is None:
                rpc = connect_discord()

            payload, last_seen = state.snapshot()
            now = time.monotonic()
            is_stale = payload is None or (now - last_seen) > STALE_TIMEOUT_SECONDS

            if is_stale:
                if not cleared_for_stale:
                    rpc.clear()
                    log.info("CS2'den veri gelmiyor, Discord durumu temizlendi.")
                    cleared_for_stale = True
                    last_sent_key = ()
                time.sleep(1.0)
                continue

            cleared_for_stale = False
            fields = build_presence_fields(payload)
            key = state_key(fields)

            enough_time_passed = (time.time() - last_sent_time) >= MIN_UPDATE_INTERVAL_SECONDS
            if fields and key != last_sent_key and enough_time_passed:
                rpc.update(
                    details=fields["details"],
                    state=fields["state"],
                    large_image=fields.get("large_image") or CS2_LOGO_IMAGE_KEY,
                    large_text=fields.get("large_text") or "Counter-Strike 2",
                    small_image=fields.get("small_image"),
                    small_text=fields.get("small_text"),
                    start=int(start_time),
                )
                log.info("Durum güncellendi: %s | %s", fields["details"], fields["state"])
                last_sent_key = key
                last_sent_time = time.time()

            time.sleep(1.0)

        except (DiscordNotFound, PipeClosed) as exc:
            log.warning("Discord'a bağlanılamadı (%s). Discord masaüstü uygulamasının "
                        "açık olduğundan emin ol. 5 sn sonra tekrar denenecek.", exc)
            rpc = None
            time.sleep(5.0)
        except KeyboardInterrupt:
            log.info("Kapatılıyor...")
            break
        except Exception as exc:  # noqa: BLE001 - script'in tek seferlik hatada ölmesini istemiyoruz
            log.exception("Beklenmeyen hata: %s", exc)
            time.sleep(3.0)

    if rpc is not None:
        try:
            rpc.clear()
            rpc.close()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
