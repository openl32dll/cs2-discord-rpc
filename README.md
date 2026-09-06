# CS2 Discord Rich Presence

Counter-Strike 2 oynarken Discord profilinde sadece "Counter-Strike 2 oynuyor"
yazısı yerine; **hangi haritada**, **hangi modda** (Rekabetçi/Premier, Yoldaş
(Wingman), Basit (Casual), Deathmatch, Silah Yarışı, Yıkım, Ko-op, Antrenman,
Özel Oyun, vb.) ve **kaçıncı roundda** olduğunu gösteren bir araç.

Round kavramı olmayan modlarda (Deathmatch, Silah Yarışı gibi) round yerine
o anki frag/ölüm sayın gösterilir.

## Nasıl çalışır?

CS2, Valve'ın **Game State Integration (GSI)** özelliği sayesinde oyun içi
durumu (harita, mod, round, skor, bomba durumu...) belirli aralıklarla
bilgisayarındaki bir HTTP adresine gönderebilir. Bu script:

1. `http://127.0.0.1:3000` adresinde küçük bir yerel sunucu açar.
2. CS2'den gelen bu veriyi okur.
3. `pypresence` kütüphanesi ile Discord masaüstü uygulamasına iletir.

## Kurulum

### 1) Discord Uygulaması oluştur

Discord, üçüncü parti scriptlerin "Rich Presence" gösterebilmesi için bir
uygulama (Client ID) oluşturmanı ister:

1. https://discord.com/developers/applications adresine git.
2. **New Application** ile yeni bir uygulama oluştur, adını istersen
   `Counter-Strike 2` koy.
3. Sol menüden **OAuth2 / General** sayfasında görünen **Application ID**
   (Client ID) değerini kopyala.

**Harita görsellerini de bu adımda yükle.** Aynı sayfada sol menüden
**Rich Presence → Art Assets** kısmına git ve `assets/maps/`
klasöründeki her PNG'yi, dosya adıyla **aynı** anahtar (key) ismiyle yükle
(uzantısız, hepsi küçük harf):

```
cs2_logo, de_dust2, de_mirage, de_inferno, de_nuke, de_overpass,
de_vertigo, de_ancient, de_anubis, de_train, de_cache, cs_office,
cs_italy, cs_agency, de_shortdust, de_lake, de_stmarc, de_grail, aim_map
```

Elinde gerçek ekran görüntüsü olmayan haritalar için (Wingman haritaları,
Agency, Aim Map gibi) bu adımı atlayabilirsin — script otomatik olarak
`cs2_logo`'ya düşer. Yeni bir görsel eklediğinde/değiştirdiğinde de aynı
anahtar ismiyle **üzerine yükleyip** script'i yeniden başlatman yeterli.

### 2) GSI config dosyasını CS2'ye tanıt

`gamestate_integration_discordrpc.cfg` dosyasını CS2'nin şu klasörüne kopyala:

```
<Steam kurulum dizini>\steamapps\common\Counter-Strike Global Offensive\game\csgo\cfg\
```

(CS2, CS:GO'nun devamı olduğu için klasör adı hâlâ `csgo`dur.)

Dosyayı kopyaladıktan sonra CS2'yi (açıksa) yeniden başlat.

### 3) Bağımlılıkları kur

```bash
pip install -r requirements.txt
```

### 4) Client ID'ni kaydet

İki seçeneğin var:

**a) Tek seferlik / test için — ortam değişkeni:**
```bash
# Windows (PowerShell)
$env:DISCORD_CLIENT_ID="BURAYA_CLIENT_ID"; python cs2_discord_rpc.py

# Linux / macOS
DISCORD_CLIENT_ID=BURAYA_CLIENT_ID python cs2_discord_rpc.py
```

**b) Kalıcı / otomatik başlatma için — config.json (önerilen):**
```bash
cp config.example.json config.json     # Windows: copy config.example.json config.json
```
`config.json` dosyasını aç, `discord_client_id` alanına Client ID'ni yaz.
Bu dosya `.gitignore`'da olduğu için repoya gitmez. Script her çalıştığında
otomatik olarak bu dosyayı okur — ortam değişkeni ayarlamana gerek kalmaz,
bu yüzden Windows başlangıcına eklemek için idealdir (bkz. aşağıdaki bölüm).

### 5) Script'i çalıştır

Discord masaüstü uygulamasının açık olduğundan emin ol, sonra:

```bash
python cs2_discord_rpc.py
```

CS2'ye girip bir maça başladığında Discord profilinde harita, mod ve round
bilgisi otomatik olarak görünmeye başlar. Ana menüdeyken veya oyundan
çıktığında durum otomatik olarak güncellenir/temizlenir.

## Windows'ta otomatik başlatma (PC/oturum açılışında)

Her seferinde elle çalıştırmak istemiyorsan, Windows'ta oturum açtığın
anda script'i arka planda (konsol penceresi açmadan) otomatik başlatan
bir Görev Zamanlayıcı (Task Scheduler) görevi kurabilirsin:

1. Önce yukarıdaki **4b) config.json** adımını tamamla (Client ID kaydedilmeden
   script çalışmaz).
2. PowerShell'i (bu repo klasörünün içindeyken) aç. Görev Zamanlayıcı bazı
   Windows kurulumlarında normal kullanıcıyla yeni görev oluşturmaya izin
   vermeyebilir — "Erişim engellendi" hatası alırsan PowerShell'i
   **yönetici olarak** (sağ tık → "Run as Administrator") yeniden aç:
   ```powershell
   powershell -ExecutionPolicy Bypass -File windows_autostart\install_autostart.ps1
   ```
3. Bu kadar. Bir sonraki oturum açışında script otomatik başlayacak.
   Hemen şimdi denemek istersen:
   ```powershell
   Start-ScheduledTask -TaskName "CS2DiscordRPC"
   ```

Kaldırmak istersen:
```powershell
powershell -ExecutionPolicy Bypass -File windows_autostart\uninstall_autostart.ps1
```

> **Not:** Görev "oturum açılışında" (`AtLogOn`) tetiklenir, "bilgisayar
> açılışında" değil — çünkü script'in konuşacağı Discord masaüstü uygulaması
> da zaten senin oturumun içinde çalışır, sistem açılışında değil. Discord
> henüz tam açılmamış olsa bile script birkaç saniyede bir otomatik
> yeniden dener, o yüzden sıralamayla ilgili bir şey yapmana gerek yok.
> Görev, script çökerse de kendini birkaç kez yeniden başlatacak şekilde
> ayarlıdır.

## Harita görselleri

Discord Rich Presence'ta iki görsel alanı var: **büyük ana görsel** ve
onun sağ alt köşesinde duran **küçük rozet**. Bu script'te:

- **Büyük görsel** her zaman `assets/maps/cs2_logo.png` — sabit CS2 logosu.
- **Küçük rozet** o an içinde bulunduğun haritayı gösterir
  (`assets/maps/<harita_kodu>.png`).
- Ana menüdeyken (henüz bir maçta değilken) sadece büyük CS2 logosu görünür,
  küçük rozet olmaz.

`assets/maps/` klasöründe her ana harita için (Dust II, Mirage, Inferno,
Nuke, Overpass, Vertigo, Ancient, Anubis, Train, Cache, Office, Italy,
Agency, Wingman haritaları, Aim Map) küçük birer PNG rozet + genel
`cs2_logo.png` bulunuyor. Şu an bunlar bu repo için üretilmiş basit
ikonlardır (bkz. aşağıdaki "Gerçek ekran görüntüsü" bölümü — kendi
görsellerinle kolayca değiştirebilirsin).

- Script, GSI'dan gelen harita adını (ör. `de_dust2`) doğrudan Discord
  Developer Portal'a yüklediğin **Art Asset anahtarı** olarak gönderiyor —
  bkz. yukarıdaki "1) Discord Uygulaması oluştur" adımı. Dış URL
  kullanılmıyor; bu, klasik masaüstü Rich Presence ile en garantili
  çalışan yöntem.
- Elimizde ikonu olmayan bir harita gelirse (yeni çıkan bir harita ya da
  community server haritası) küçük rozet de otomatik olarak `cs2_logo`'ya
  düşer.
- Yeni bir harita eklemek / ikonları yeniden üretmek istersen:
  `assets/generate_map_icons.py` script'ini (Pillow gerektirir) düzenleyip
  tekrar çalıştırabilirsin.

### Gerçek ekran görüntüsü kullanmak istersen

Valve'ın oyun içi ekran görüntülerini bu repoya hazır olarak koymuyoruz
(telifli içerik). Ama **kendi aldığın** ekran görüntülerini kullanmak
tamamen senin tercihin ve çok kolay:

1. CS2'de bir maça gir, `F12` (Steam ekran görüntüsü) ile görüntü al.
2. Görüntüyü `assets/screenshots_raw/<harita_kodu>.jpg` olarak kaydet
   (ör. `assets/screenshots_raw/de_mirage.jpg`; geçerli harita kodları
   yukarıdaki listede).
3. `python assets/import_screenshots.py` çalıştır.

Script, görüntüyü otomatik olarak 1024x576 (16:9) boyutuna ortalayarak
kırpıp `assets/maps/<harita_kodu>.png` olarak kaydeder; `cs2_discord_rpc.py`
tarafında hiçbir değişikliğe gerek kalmadan bu yeni görsel kullanılmaya
başlar.

## Desteklenen modlar

| GSI mod anahtarı      | Discord'da görünen ad     | Round gösterimi |
|------------------------|----------------------------|------------------|
| `competitive`           | Rekabetçi                  | Round X/24       |
| `scrimcomp5v5`          | Premier                    | Round X/24       |
| `scrimcomp2v2`          | Yoldaş (Wingman)            | Round X/16       |
| `casual`                | Basit                      | Round X          |
| `deathmatch`            | Deathmatch                 | Frag / ölüm      |
| `gungameprogressive`    | Silah Yarışı (Arms Race)   | Frag / ölüm      |
| `gungametrbomb`         | Yıkım (Demolition)         | Round X          |
| `skirmish`              | Uçan Keşif Nişancısı        | Round X          |
| `cooperative`           | Ko-op Görev                | Frag / ölüm      |
| `training`              | Antrenman                  | Frag / ölüm      |
| `custom`                | Özel Oyun                  | Round X          |

Listede olmayan yeni bir mod eklenirse script "Bilinmeyen Mod" olarak
gösterir; `cs2_discord_rpc.py` içindeki `MODE_INFO` sözlüğüne yeni satır
ekleyerek kolayca genişletilebilir.

> **Not:** `competitive`/`scrimcomp5v5` için 24, `scrimcomp2v2` için 16
> round varsayılan matchmaking ayarlarına (MR12 / MR8) göre verilmiştir.
> Özel sunucularda (community server) bu limit farklıysa sadece geçerli
> round numarası gösterilir.
