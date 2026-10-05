"""Real HTTP smoke test; never edits pre-existing records or images."""
import hashlib
import json
import sqlite3
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "http://127.0.0.1:8001"


def snapshot():
    with sqlite3.connect(f"file:{(ROOT / 'wardrobe.db').as_posix()}?mode=ro", uri=True) as db:
        rows = db.execute("SELECT * FROM clothes ORDER BY id").fetchall()
        schema = db.execute("PRAGMA table_info(clothes)").fetchall()
    images = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (ROOT / "uploads").iterdir() if p.is_file()}
    return rows, schema, images


def request(path, method="GET", data=None, content_type=None):
    headers = {}
    if isinstance(data, dict):
        data = json.dumps(data).encode()
        content_type = "application/json"
    if content_type:
        headers["Content-Type"] = content_type
    try:
        response = urlopen(Request(BASE_URL + path, data=data, headers=headers, method=method), timeout=15)
    except HTTPError as error:
        response = error
    with response:
        body = response.read()
        if "application/json" in response.headers.get("Content-Type", ""):
            body = json.loads(body)
        return response.status, body


def run():
    before = snapshot()
    marker = f"demo-smoke-{uuid4()}"
    temporary_ids = []
    image_path = None
    results = {}
    try:
        for path in ("/", "/docs", "/clothes"):
            status, _ = request(path)
            assert status == 200, (path, status)
            results[path] = status
        _, original = request("/clothes")
        assert len(original["clothes"]) == len(before[0])
        for item in original["clothes"]:
            assert request(f"/clothes/{item['id']}")[0] == 200
            if item["image_path"]:
                assert request("/" + item["image_path"])[0] == 200
        boundary = f"Wardrobe{uuid4().hex}"
        data = bytearray()
        fields = [("name", marker), ("category", "shirt"), ("color", "navy"),
                  ("seasons", "spring"), ("seasons", "summer"), ("style", "smart_casual"),
                  ("fit", "regular"), ("material", "cotton"), ("formality", "5")]
        for key, value in fields:
            data.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        image = b'<svg xmlns="http://www.w3.org/2000/svg" width="240" height="300"><rect width="240" height="300" fill="#efe9dc"/><path d="M80 50L40 80L60 125L80 115V245H160V115L180 125L200 80L160 50L140 65H100Z" fill="#45546b"/></svg>'
        data.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="demo.svg"\r\nContent-Type: image/svg+xml\r\n\r\n'.encode())
        data.extend(image)
        data.extend(f"\r\n--{boundary}--\r\n".encode())
        status, response = request("/clothes", "POST", bytes(data), f"multipart/form-data; boundary={boundary}")
        assert status in (200, 201), response
        created = response["clothing"]
        temporary_ids.append(created["id"])
        image_path = created["image_path"]
        assert request("/" + image_path) == (200, image)
        results["POST + image"] = status
        path = f"/clothes/{created['id']}"
        status, updated = request(path, "PATCH", {"name": marker + "-edited", "formality": 6, "seasons": ["winter", "autumn"]})
        assert status == 200 and updated["image_path"] == image_path
        assert updated["seasons"] == ["winter", "autumn"] and updated["season"] == "winter"
        assert updated["category"] == created["category"] and updated["style"] == created["style"]
        assert request("/" + image_path)[1] == image
        results["PATCH partial + image preserved"] = status
        for invalid in (0, 11):
            assert request(path, "PATCH", {"formality": invalid})[0] == 422
        assert request("/clothes/99999999", "PATCH", {"name": "Missing"})[0] == 404
        for field, value in (("category", "shirt"), ("color", "navy"), ("season", "winter")):
            status, filtered = request(f"/clothes?{field}={value}")
            assert status == 200 and created["id"] in [i["id"] for i in filtered["clothes"]]
        results["filters + validation"] = "PASS"
        for season in ("summer", "winter"):
            status, recommendations = request(f"/recommendations?season={season}&limit=3")
            assert status == 200 and 0 < len(recommendations["recommendations"]) <= 3
            assert all(isinstance(r["top"]["seasons"], list) for r in recommendations["recommendations"])
        results["recommendations"] = "PASS"
        assert request(path, "DELETE")[0] == 200
        temporary_ids.remove(created["id"])
        assert request(path)[0] == 404 and not (ROOT / image_path).exists()
        results["DELETE + image cleanup"] = "PASS"
    finally:
        # A failed POST can still have committed a record: locate only our unique marker.
        status, response = request("/clothes")
        if status == 200:
            temporary_ids.extend(i["id"] for i in response["clothes"] if i["name"].startswith(marker))
        for item_id in set(temporary_ids):
            request(f"/clothes/{item_id}", "DELETE")
        after = snapshot()
        assert after == before, "Permanent rows, schema or images changed"
    results["permanent rows before/after"] = [len(before[0]), len(after[0])]
    results["permanent photos + schema"] = "UNCHANGED"
    print(json.dumps(results, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    run()
