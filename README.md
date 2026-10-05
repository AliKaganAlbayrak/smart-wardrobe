# Smart Wardrobe

Kıyafetlerini fotoğrafları ve detaylarıyla saklayan, mevcut gardırobundan
açıklanabilir kombinler üreten bir yerel web uygulaması.

## Özellikler

- Fotoğraflı gardırop; kategori, renk, mevsim ve stil filtreleri.
- Kıyafet ekleme, önceden doldurulmuş panelde düzenleme ve onaylı silme.
- Çoklu mevsim, legacy `season` uyumluluğu ve 1–10 resmiyet doğrulaması.
- Renk, mevsim, stil ve resmiyet puanlarıyla deterministic kombin önerileri.
- Explicit **Kombin Oluştur** akışı; loading, hata, retry ve başarı bildirimleri.
- Desktop, tablet ve mobil ekranlara uyarlanan React arayüzü.

## Mimari ve stack

```text
app/
  main.py                  # FastAPI, CORS, /uploads static serving
  database.py, models.py   # SQLAlchemy 2 + SQLite
  schemas.py              # Pydantic validation
  routers/                # clothes ve recommendations HTTP endpointleri
  services/               # clothing, image, recommendation iş mantığı
frontend/src/
  components/             # Kartlar, ortak form alanları, modal, feedback
  pages/                  # Gardırop, kıyafet ekleme, kombin önerileri
  services/               # Merkezi API istemcisi ve görüntüleme etiketleri
  types/, styles/         # TypeScript tipleri ve plain CSS
tests/                    # Backend unit ve smoke testleri
```

Backend: Python 3.10+, FastAPI, Uvicorn, SQLAlchemy, Pydantic, SQLite,
python-multipart. Frontend: React, TypeScript, Vite; ağır UI framework yok.

SQLite ve upload yolları proje köküne göre çözülür; çalışma dizinine bağımlı
değildir. `wardrobe.db`, `uploads/`, virtual environment ve build/cache
dosyaları Git dışında tutulur.

## Yerelde çalıştırma

Proje kökünde sanal ortam yoksa oluşturun ve bağımlılıkları kurun:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

Bu projede ortam üst klasördeyse aynı komutlarda
`..\.venv\Scripts\python.exe` kullanın. Aktivasyon veya PowerShell
Execution Policy değişikliği gerekmez. Ortam etkinse eşdeğer komut:

```sh
python -m uvicorn app.main:app --reload --port 8001
```

Ayrı bir terminalde (Node.js 20.19+ / 22.12+):

```sh
cd frontend
npm install
npm run dev
```

- [Web arayüzü](http://127.0.0.1:5173)
- [API](http://127.0.0.1:8001)
- [Swagger](http://127.0.0.1:8001/docs)

Frontend varsayılan API adresi `http://127.0.0.1:8001`; geliştirme için
`VITE_API_BASE_URL` ile değiştirilebilir. CORS, localhost/127.0.0.1:5173
origin'lerine izin verir.

## API

| Metot | Endpoint | Davranış |
| --- | --- | --- |
| GET | `/` | Sağlık mesajı |
| GET | `/clothes` | Liste; optional category, color, season |
| GET | `/clothes/{id}` | Tek kıyafet; yoksa 404 |
| POST | `/clothes` | Multipart metadata ve optional image |
| PATCH | `/clothes/{id}` | JSON partial update; ClothingResponse döner |
| DELETE | `/clothes/{id}` | Kayıt ve varsa fotoğrafı siler |
| GET | `/recommendations` | season ve limit ile kombinler |
| GET | `/uploads/{filename}` | UUID isimli kullanıcı görseli |

POST alanları: `name, category, color, season/seasons, style, fit, material,
formality, image`. Birden fazla mevsim için formda `seasons` alanını tekrar
gönderin. API response'unda `seasons` her zaman string listesi olarak döner.

PATCH örneği:

```http
PATCH /clothes/7
Content-Type: application/json

{
  "name": "Krem keten gömlek",
  "seasons": ["spring", "summer"],
  "style": "smart_casual",
  "formality": 5
}
```

Gönderilmeyen alanlar ve `image_path` korunur. `seasons` güncellenirse legacy
`season` ilk mevsime eşitlenir. `style/fit/material` null ile temizlenebilir.
Zorunlu alanlarda null/boş değer, boş mevsim listesi, izin verilmeyen alan
ve 1–10 dışındaki formality için 422; bulunamayan ID için 404 döner.
PATCH fotoğraf değiştirmez.

## Kombin motoru · V2.2

Bir üst (`tshirt/shirt/polo/sweater/hoodie`), bir alt
(`pants/jeans/shorts`) ve `shoes` üzerinden kombinler üretilir.
Ceketler katman olarak kullanılmaz. Çoklu mevsim, `all-season` ve legacy
fallback desteklenir. Eksik bilgiler hata oluşturmaz; tarafsız puanlar
kullanılır ve arayüzde anlaşılır notlarla belirtilir.

```text
total_score = color × 0.35 + season × 0.25 + style × 0.25 + formality × 0.15
GET /recommendations?season=summer&limit=3
```

Limit 1–20 (varsayılan 3); istenen mevsim spring/summer/autumn/fall/winter.
Yetersiz kategoride boş liste döner. Bu sürümde skor algoritması değişmemiştir.

## Doğrulama

Proje kökünde doğru venv interpreter'ıyla:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
..\.venv\Scripts\python.exe -c "from tests.test_smoke import test_api_smoke_and_metadata_cleanup; test_api_smoke_and_metadata_cleanup()"
# API çalışırken: yalnızca geçici kıyafet/görsel oluşturur ve finally ile temizler.
..\.venv\Scripts\python.exe tests/smoke_live.py
```

Frontend:

```sh
cd frontend
npm test
npm run build
```

PATCH unit testleri izole in-memory SQLite kullanır. Mevcut recommendation
testleri ve canlı smoke testi oluşturdukları geçici kayıtları temizler.
`tests/smoke_live.py` ayrıca kalıcı kayıtları, tablo şemasını ve fotoğraf
hash'lerini başlangıç ve bitişte karşılaştırır.

## Mevcut sınırlar ve roadmap

Tek kullanıcılı yerel demo; authentication ve production deployment yok.
Görsel yükleme mevcut MIME kontrolüne dayanır; production öncesi boyut limiti
ve dosya içeriği doğrulaması gerekli. Çok büyük gardıroplar için kombin
hesaplamasının ve listelemenin ölçeklendirilmesi planlanabilir.
Sonraki adımlar: pagination, accessibility test otomasyonu, deployment
konfigürasyonu ve kullanıcı tercihleri. ML, weather ve auth bu sürümün
kapsamında değildir.
