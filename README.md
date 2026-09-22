# Smart Wardrobe

## Project Overview

Smart Wardrobe, kullanıcının kıyafetlerini kaydetmesini ve ileride hava durumu,
renk uyumu, mevsim ve kişisel tercihlere göre kombin önerileri almasını sağlayacak
kişisel gardırop uygulamasıdır. Mevcut sürüm, kıyafet kaydetme ve listeleme
işlemleri için bir REST API sunar. Kombin önerileri henüz geliştirme aşamasına
alınmamış, yol haritasında planlanmıştır.

## Current Features

- İsim, kategori, renk ve mevsim bilgileriyle kıyafet kaydetme.
- Kayıtlı kıyafetleri listeleme.
- SQLite veritabanında kalıcı veri saklama.
- Pydantic ile istek verilerinin doğrulanması.
- FastAPI tarafından oluşturulan etkileşimli API dokümantasyonu.

| Metot | Endpoint | Açıklama |
| --- | --- | --- |
| GET | `/` | API'nin çalıştığını belirten mesajı döndürür. |
| POST | `/clothes` | Yeni bir kıyafet kaydeder. |
| GET | `/clothes` | Kayıtlı kıyafetleri listeler. |

## Tech Stack

- **Python** — uygulama dili.
- **FastAPI** — REST API çatısı.
- **Uvicorn** — ASGI sunucusu.
- **SQLAlchemy 2.x** — veritabanı modelleri ve erişimi.
- **Pydantic** — veri doğrulama.
- **SQLite** — yerel veritabanı; Python ile birlikte gelir.

## Installation

Python 3.10 veya üzeri önerilir. Terminali proje kök dizininde açın.

1. Sanal ortam oluşturun:

   ```sh
   python -m venv .venv
   ```

2. Sanal ortamı etkinleştirin:

   Windows PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   macOS / Linux:

   ```sh
   source .venv/bin/activate
   ```

3. Bağımlılıkları yükleyin:

   ```sh
   python -m pip install -r requirements.txt
   ```

## Running the API

Proje kök dizininde, sanal ortam etkin durumdayken geliştirme sunucusunu başlatın:

```sh
python -m uvicorn main:app --reload
```

- [API ana sayfası](http://127.0.0.1:8000/)
- [Swagger UI](http://127.0.0.1:8000/docs)
- [ReDoc](http://127.0.0.1:8000/redoc)

Uygulama ilk açılışta `wardrobe.db` dosyasını ve gerekli tabloları otomatik
oluşturur. Veritabanı ve gelecekte kullanılacak `uploads/` dizini Git'e dahil edilmez.

Swagger UI üzerinden `POST /clothes` için örnek istek gövdesi:

```json
{
  "name": "Beyaz tişört",
  "category": "Üst giyim",
  "color": "Beyaz",
  "season": "Yaz"
}
```

## Roadmap

- Kıyafet güncelleme ve silme.
- Kıyafet fotoğrafı yükleme.
- Hava durumu verilerinin entegrasyonu.
- Renk uyumu ve mevsime göre kombin önerileri.
- Kişisel tercihlere göre önerilerin özelleştirilmesi.
- Gardırop yönetimi için kullanıcı arayüzü.
