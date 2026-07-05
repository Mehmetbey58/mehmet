"""One-off yardımcı script (alternatif yöntem).

create_session.py, Instagram'a kullanıcı adı/şifre ile "programatik"
giriş yapar; bu tür otomatik girişler Instagram tarafından güvenlik
kontrolüne (checkpoint) takılabiliyor. Bu script bunun yerine, bu
bilgisayarda zaten normal şekilde tarayıcıdan (Chrome/Firefox) giriş
yapılmış olan oturumun çerezlerini kullanır - Instagram bu oturuma
zaten güveniyor, bu yüzden checkpoint tetiklenme ihtimali çok daha
düşüktür.

Önkoşul:
    1. Bu bilgisayarda Chrome veya Firefox ile instagram.com'a normal
       şekilde giriş yapmış olun (tarayıcıdan, elle).
    2. pip install browser-cookie3

Kullanım:
    python create_session_from_browser.py chrome
    python create_session_from_browser.py firefox
"""

from __future__ import annotations

import sys

import instaloader

from config import load_settings


def main() -> None:
    browser = sys.argv[1] if len(sys.argv) > 1 else "chrome"

    try:
        import browser_cookie3
    except ImportError:
        print("Önce şunu çalıştırın: pip install browser-cookie3")
        raise SystemExit(1)

    loader_fn = getattr(browser_cookie3, browser, None)
    if loader_fn is None:
        print(f"Desteklenmeyen tarayıcı: {browser!r} (chrome veya firefox kullanın)")
        raise SystemExit(1)

    settings = load_settings()

    cookies = loader_fn(domain_name="instagram.com")
    loader = instaloader.Instaloader(quiet=True)
    loader.context._session.cookies.update({cookie.name: cookie.value for cookie in cookies})

    username = loader.test_login()
    if not username:
        print(
            f"Oturum bulunamadı. {browser} içinde instagram.com'a giriş yapmış "
            "olduğunuzdan emin olun ve tekrar deneyin."
        )
        raise SystemExit(1)

    loader.context.username = username
    settings.ig_session_path.parent.mkdir(parents=True, exist_ok=True)
    loader.save_session_to_file(str(settings.ig_session_path))

    print(f"@{username} için oturum tarayıcı çerezlerinden oluşturuldu: {settings.ig_session_path}")
    print("Bu dosyayı sunucudaki aynı yola (.env içindeki IG_SESSION_PATH) kopyalayın.")


if __name__ == "__main__":
    main()
