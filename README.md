# Smart Wardrobe

## Project Overview

Smart Wardrobe, kullanıcının kıyafetlerini kaydetmesini ve ileride hava durumu,
renk uyumu, mevsim ve kişisel tercihlere göre kombin önerileri almasını sağlayacak
kişisel gardırop uygulamasıdır. Mevcut sürüm, kıyafet kaydetme ve listeleme
işlemleri için bir REST API sunar.

## Current Features

- İsim, kategori, renk ve mevsim bilgileriyle, isteğe bağlı görsel dosyasıyla kıyafet kaydetme.
- Kayıtlı kıyafetleri listeleme.
- SQLite veritabanında kalıcı veri saklama.
- Multipart form verilerinin ve görsel yüklemelerinin desteklenmesi.
- FastAPI tarafından oluşturulan etkileşimli API dokümantasyonu.

| Metot | Endpoint | Açıklama |
| --- | --- | --- |
| GET | `/` | API'nin çalıştığını belirten mesajı döndürür. |
| POST | `/clothes` | Yeni bir kıyafet kaydeder. |
| GET | `/clothes` | Kayıtlı kıyafetleri listeler; kategori, renk ve mevsime göre filtrelenebilir. |
| GET | `/clothes/{clothing_id}` | ID ile tek bir kıyafeti getirir. |
| DELETE | `/clothes/{clothing_id}` | Kıyafeti ve varsa görselini siler. |

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

```text
POST /clothes (multipart/form-data)

name=Beyaz tişört
category=Üst giyim
color=Beyaz
season=Yaz
image=<bir görsel dosyası>
```

Görsel yüklenirse proje kökündeki `uploads/` klasörüne UUID tabanlı benzersiz
dosya adıyla kaydedilir ve kaydın `image_path` alanında tutulur. Görsel alanı
isteğe bağlıdır.

Yüklenen görseller `/uploads/<dosya_adı>` URL'si üzerinden servis edilir.

### Swagger test senaryoları

Uygulamayı çalıştırdıktan sonra [Swagger UI](http://127.0.0.1:8001/docs)
üzerinden:

1. `POST /clothes` ile form alanlarını ve isteğe bağlı bir görseli gönderin.
2. `GET /clothes` ile tüm kayıtları listeleyin.
3. `GET /clothes?category=shirt&color=cream` ile filtreleri deneyin.
4. `GET /clothes/{clothing_id}` ile oluşturduğunuz kaydı getirin.
5. `DELETE /clothes/{clothing_id}` ile kaydı silin; görsel dosyasının da silindiğini kontrol edin.
6. Olmayan bir ID için GET ve DELETE isteklerinde `404` bekleyin.
7. Filtreleri boş bıraktığınızda (`/clothes`) tüm kayıtların dönmesini bekleyin.

Çalıştırma komutu:

```powershell
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001
```

## Roadmap

- Kıyafet güncelleme ve silme.
- Hava durumu verilerinin entegrasyonu.
- Renk uyumu ve mevsime göre kombin önerileri.
- Kişisel tercihlere göre önerilerin özelleştirilmesi.
- Gardırop yönetimi için kullanıcı arayüzü.
