# Instagram Takip Telegram Botu

Belirlediğiniz Instagram hesaplarını takip eden, yeni gönderi/reel/hikaye
paylaşıldığında bunları Telegram'a ileten bir bot.

## Instagram güvenliği için en önemli kural

Bot Instagram'a **yalnızca** şu üç durumda istek gönderir:

1. `/anlik` komutu çalıştırıldığında (tüm hesaplar kontrol edilir)
2. `/kontrol kullaniciadi` komutu çalıştırıldığında (tek hesap kontrol edilir)
3. Her gün `CHECK_TIME` içinde ayarlanan saatte (varsayılan `09:00`)

Bunların dışında hiçbir arka plan döngüsü, polling veya periyodik istek
yoktur. Instagram oturumu diske kaydedilir (`IG_SESSION_PATH`) ve yalnızca
gerektiğinde (oturum yoksa veya geçersiz olduğunda) yeniden giriş yapılır.

## Kurulum

### 1. Sanal ortam oluşturma

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Bağımlılıkları kurma

```bash
pip install -r requirements.txt
```

### 3. .env dosyasını oluşturma

```bash
cp .env.example .env
```

`.env` dosyasını açıp aşağıdaki alanları doldurun:

| Değişken           | Açıklama                                                        |
|--------------------|------------------------------------------------------------------|
| `BOT_TOKEN`        | @BotFather'dan alınan Telegram bot token'ı                       |
| `ADMIN_IDS`        | Botu kullanabilecek Telegram kullanıcı ID'leri (virgülle ayrık)   |
| `IG_USERNAME`      | Bot'un giriş yapacağı Instagram kullanıcı adı                     |
| `IG_PASSWORD`      | Instagram şifresi                                                 |
| `CHECK_TIME`       | Günlük otomatik kontrol saati (varsayılan `09:00`)                |
| `DATABASE_PATH`    | SQLite veritabanı dosya yolu (varsayılan `data/bot.db`)           |
| `IG_SESSION_PATH`  | Instagram oturum dosyası yolu (varsayılan `data/ig_session`)      |
| `LOG_DIR`          | Log dosyalarının yazılacağı klasör (varsayılan `logs`)            |
| `POST_FETCH_LIMIT` | Her kontrolde hesap başına bakılacak en yeni gönderi sayısı       |
| `TIMEZONE`         | Günlük görevin çalışacağı zaman dilimi                            |

> `IG_USERNAME`/`IG_PASSWORD` kendi ana hesabınız yerine bunun için
> ayrılmış ikincil bir hesap olması önerilir. İki adımlı doğrulama
> açıksa ilk girişi lokal ortamınızda tamamlayıp oturum dosyasını
> (`IG_SESSION_PATH`) sunucuya taşıyabilirsiniz.

### 4. Botu çalıştırma

```bash
python bot.py
```

Bot, Telegram komutlarını dinlemeye başlar ve günlük kontrol görevini
`CHECK_TIME` saatine planlar.

## Komutlar

| Komut                     | Açıklama                                             |
|---------------------------|-------------------------------------------------------|
| `/start`                  | Bot hakkında bilgi ve komut listesi                  |
| `/ekle kullaniciadi`      | Takip listesine hesap ekler                          |
| `/sil kullaniciadi`       | Takip listesinden hesap kaldırır                     |
| `/liste`                  | Takip edilen tüm hesapları listeler (silme butonuyla)|
| `/anlik`                  | Tüm hesapları şimdi kontrol eder                     |
| `/kontrol kullaniciadi`   | Sadece belirtilen hesabı kontrol eder                |
| `/profil kullaniciadi`    | Profil fotoğrafı, ad, bio, takipçi/takip/gönderi sayısı |

Argüman verilmeden çağrılan `/ekle`, `/sil` ve `/profil` komutları,
kullanıcı adını ayrı bir mesajla sormak üzere bir iptal butonu gösterir.

## Gönderi gönderme mantığı

- **Fotoğraf / Video / Reel:** önce medya gönderilir, ardından (varsa)
  açıklama `📝` ön ekiyle **ayrı bir mesaj** olarak gönderilir. Açıklama
  yoksa ikinci mesaj hiç gönderilmez.
- **Carousel:** birden fazla medya, Telegram `MediaGroup` ile tek seferde
  gönderilir; açıklama yine ayrı bir mesaj olarak gelir.
- **Hikaye (Story):** medya doğrudan gönderilir; hikayede metin/caption
  varsa mümkün olduğunca medyanın caption'ı olarak eklenir (ayrı mesaj
  gönderilmez).

## Tekrar gönderim koruması

Her içerik Instagram Media ID'si ile kaydedilir. Bir içerik daha önce
gönderildiyse (`sent_messages` tablosunda kaydı varsa) bir daha
gönderilmez.

## Veritabanı (SQLite)

| Tablo           | Amaç                                                          |
|------------------|----------------------------------------------------------------|
| `accounts`       | Takip edilen Instagram kullanıcı adları                       |
| `posts`          | Keşfedilen gönderiler (fotoğraf/carousel) önbelleği            |
| `reels`          | Keşfedilen reels önbelleği                                     |
| `stories`        | Keşfedilen hikayeler önbelleği                                 |
| `sent_messages`  | Telegram'a fiilen gönderilmiş içerikler (tekrar gönderim koruması buradan yapılır) |
| `settings`       | Küçük anahtar/değer ayarları (ör. son kontrol zamanı)          |

Veritabanı dosyası `DATABASE_PATH` ile belirtilen konumda otomatik
oluşturulur; elle bir migration çalıştırmanız gerekmez.

## Loglama

`LOG_DIR` altında üç ayrı log dosyası tutulur:

- `info.log` - sadece INFO seviyesindeki kayıtlar
- `warning.log` - sadece WARNING seviyesindeki kayıtlar (ör. yeniden deneme uyarıları)
- `error.log` - ERROR ve üzeri kayıtlar

Ayrıca konsola da aynı anda log basılır.

## Hata yönetimi

- Instagram bağlantı hataları ve rate limit durumlarında istekler
  otomatik olarak artan bekleme süreleriyle (5s, 10s, ...) yeniden
  denenir.
- Bir hesabın kontrolü başarısız olsa bile diğer hesapların kontrolü
  devam eder; bot asla çökmez, hata `error.log`'a yazılır ve ilgili
  komutu çalıştıran kullanıcıya bilgi verilir.

## Proje yapısı

```
bot.py                 # Giriş noktası
config.py               # .env tabanlı ayarlar
database.py             # SQLite erişim katmanı
instagram.py             # Instaloader tabanlı Instagram istemcisi
scheduler.py             # Kontrol mantığı (ContentMonitor) + günlük görev
keyboards.py             # Inline klavyeler
states.py                # FSM durumları
handlers/
    commands.py          # Komut handler'ları
    callbacks.py          # Inline buton callback handler'ları
models/
    instagram_models.py  # İçerik/veri modelleri
utils/
    logger.py             # Log yapılandırması
    retry.py              # Backoff'lu yeniden deneme yardımcı fonksiyonu
    senders.py            # Telegram'a medya + açıklama gönderme mantığı
logs/                    # Log dosyaları (git'e dahil değil)
data/                    # SQLite veritabanı + Instagram oturum dosyası (git'e dahil değil)
```
