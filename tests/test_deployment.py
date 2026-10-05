"""Deployment config and startup tests use a disposable directory, not user data."""
import json
import os
import socket
import shlex
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.config import PROJECT_ROOT, data_directory, frontend_origins


class DeploymentTests(unittest.TestCase):
    def test_local_storage_default_and_relative_paths(self):
        self.assertEqual(data_directory(""), PROJECT_ROOT)
        self.assertEqual(data_directory("storage"), PROJECT_ROOT / "storage")
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(data_directory(directory), Path(directory).resolve())

    def test_explicit_origins_and_validation(self):
        self.assertIn("http://127.0.0.1:5173", frontend_origins(""))
        self.assertEqual(frontend_origins(" https://demo.netlify.app/,https://demo.netlify.app "),
                         ["https://demo.netlify.app"])
        for value in ("*", "file:///tmp", "https://demo.netlify.app/path", "https://user:pass@example.com"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                frontend_origins(value)

    def test_production_cors_preflight(self):
        app = FastAPI()
        app.add_middleware(CORSMiddleware, allow_origins=frontend_origins("https://demo.netlify.app"),
                           allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
        with TestClient(app) as client:
            headers = {"Origin": "https://demo.netlify.app", "Access-Control-Request-Method": "PATCH",
                       "Access-Control-Request-Headers": "content-type"}
            response = client.options("/clothes/1", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["access-control-allow-origin"], headers["Origin"])
            response = client.options("/clothes/1", headers={**headers, "Origin": "https://other.example"})
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("access-control-allow-origin", response.headers)

    def test_app_startup_shared_storage_upload_and_cors(self):
        code = '''
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.database import DATABASE_PATH
from app.config import UPLOADS_DIR
from app.services.image_service import UPLOADS_DIR as IMAGE_DIR
assert UPLOADS_DIR == IMAGE_DIR == DATABASE_PATH.parent / "uploads"
with TestClient(app) as client:
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/clothes").json()["clothes"] == []
    headers={"Origin":"https://demo.netlify.app","Access-Control-Request-Method":"PATCH"}
    response=client.options("/clothes/1",headers=headers)
    assert response.status_code==200
    assert response.headers["access-control-allow-origin"]==headers["Origin"]
    data=dict(name="Deploy Test",category="shirt",color="cream",season="spring",style="casual",formality="5")
    response=client.post("/clothes",data=data,files={"image":("test.svg",b'<svg xmlns="http://www.w3.org/2000/svg"/>',"image/svg+xml")})
    assert response.status_code==200
    item=response.json()["clothing"]
    assert client.get("/"+item["image_path"]).status_code==200
    assert client.delete("/clothes/"+str(item["id"])).status_code==200
    assert not list(UPLOADS_DIR.iterdir())
print(json.dumps({"startup":"PASS","shared_storage":"PASS","CORS":"PASS"}))
'''
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, "WARDROBE_DATA_DIR": directory,
                   "FRONTEND_ORIGINS": "https://demo.netlify.app", "PYTHONPATH": str(PROJECT_ROOT)}
            result = subprocess.run([sys.executable, "-c", code], cwd=directory, env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["startup"], "PASS")

    def test_uvicorn_production_start_command(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.close()
            env = {**os.environ, "WARDROBE_DATA_DIR": directory,
                   "FRONTEND_ORIGINS": "https://demo.netlify.app", "PYTHONPATH": str(PROJECT_ROOT)}
            command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                       "--port", str(port), "--workers", "1"]
            process = subprocess.Popen(command, cwd=directory, env=env, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.PIPE,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail(process.stderr.read().decode())
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                            self.assertEqual(response.status, 200)
                        break
                    except URLError:
                        time.sleep(0.05)
                else:
                    self.fail("Uvicorn did not start within 10 seconds")
                with urlopen(f"http://127.0.0.1:{port}/docs", timeout=2) as response:
                    self.assertEqual(response.status, 200)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                process.stderr.close()

    def test_frontend_host_config_and_production_url_guard(self):
        with (PROJECT_ROOT / "netlify.toml").open("rb") as file:
            config = tomllib.load(file)
        self.assertEqual(config["build"]["base"], "frontend")
        self.assertEqual(config["build"]["publish"], "dist")
        guard = shlex.split(config["context"]["production"]["command"].split(" && ")[0])
        for url, success in (("", False), ("http://127.0.0.1:8001", False),
                             ("https://wardrobe-api.example", True)):
            with self.subTest(url=url):
                result = subprocess.run(guard, env={**os.environ, "VITE_API_BASE_URL": url},
                                        capture_output=True, timeout=10)
                self.assertEqual(result.returncode == 0, success)


if __name__ == "__main__":
    unittest.main()
