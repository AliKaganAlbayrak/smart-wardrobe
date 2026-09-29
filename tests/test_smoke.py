from io import BytesIO

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import ClothingDB


client = TestClient(app)


def _count_clothes() -> int:
    db = SessionLocal()
    try:
        return db.query(ClothingDB).count()
    finally:
        db.close()


def test_api_smoke_and_metadata_cleanup():
    initial_count = _count_clothes()

    assert client.get("/").status_code == 200
    assert client.get("/clothes").status_code == 200
    assert client.get("/clothes/1").status_code == 200

    valid_payload = {
        "name": "Pytest Smoke Shirt",
        "category": "shirt",
        "color": "navy",
        "seasons": ["spring", "summer"],
        "style": "smart_casual",
        "fit": "regular",
        "material": "cotton",
        "formality": "5",
    }
    response = client.post("/clothes", data=valid_payload)
    assert response.status_code in {200, 201}
    created = response.json()["clothing"]
    assert isinstance(created["seasons"], list)
    assert created["seasons"] == ["spring", "summer"]

    assert client.get(f"/clothes/{created['id']}").status_code == 200
    assert client.post(
        "/clothes",
        data={**valid_payload, "name": "Pytest Invalid Low", "formality": "0"},
    ).status_code == 422
    assert client.post(
        "/clothes",
        data={**valid_payload, "name": "Pytest Invalid High", "formality": "11"},
    ).status_code == 422

    image_response = client.post(
        "/clothes",
        data={**valid_payload, "name": "Pytest Image"},
        files={"image": ("pytest.jpg", BytesIO(b"test-image"), "image/jpeg")},
    )
    assert image_response.status_code in {200, 201}
    image_item = image_response.json()["clothing"]
    assert image_item["image_path"].startswith("uploads/")

    assert client.delete(f"/clothes/{created['id']}").status_code == 200
    assert client.delete(f"/clothes/{image_item['id']}").status_code == 200
    assert _count_clothes() == initial_count
