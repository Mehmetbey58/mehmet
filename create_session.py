"""One-off yardımcı script.

Instagram, veri merkezi/VPS IP'lerinden yapılan programatik girişleri sık
sık reddeder (ör. "Unexpected null login result" hatası). Çözüm: bu
script'i normal bir ev/mobil internet bağlantısından çalıştırıp oturumu
diske kaydedin, ardından oluşan dosyayı sunucudaki IG_SESSION_PATH
konumuna kopyalayın. Bot, dosya orada bulunduğu sürece tekrar
kullanıcı adı/şifre ile giriş yapmaya çalışmaz.

Kullanım:
    python create_session.py
"""

from __future__ import annotations

import getpass

import instaloader

from config import load_settings


def main() -> None:
    settings = load_settings()
    username = settings.ig_username
    password = settings.ig_password or getpass.getpass(f"@{username} şifresi: ")

    loader = instaloader.Instaloader(quiet=True)
    loader.login(username, password)  # İki adımlı doğrulama açıksa kod terminalden sorulur.

    settings.ig_session_path.parent.mkdir(parents=True, exist_ok=True)
    loader.save_session_to_file(str(settings.ig_session_path))

    print(f"Oturum kaydedildi: {settings.ig_session_path}")
    print("Bu dosyayı sunucudaki aynı yola (.env içindeki IG_SESSION_PATH) kopyalayın.")


if __name__ == "__main__":
    main()
