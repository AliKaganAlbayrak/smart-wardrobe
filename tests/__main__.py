"""`python -m tests` isolates even legacy tests from real DB/uploads/credentials."""
import os
import tempfile
import unittest
from pathlib import Path


def main() -> int:
    persistence_vars = ("DATABASE_URL", "APP_ENV", "RENDER", "IMAGE_STORAGE", "SUPABASE_URL",
                        "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_STORAGE_BUCKET",
                        "WARDROBE_DATA_DIR")
    previous = {key: os.environ.get(key) for key in persistence_vars}
    with tempfile.TemporaryDirectory(prefix="wardrobe-tests-") as directory:
        try:
            for key in persistence_vars:
                os.environ.pop(key, None)
            os.environ["WARDROBE_DATA_DIR"] = directory
            suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            return 0 if result.wasSuccessful() else 1
        finally:
            from app.database import engine
            engine.dispose()
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
