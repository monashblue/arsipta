"""Entry point ARSIPTA; database dan data kerja disimpan di folder data pengguna."""
import os
import shutil
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    RESOURCE_DIR = Path(sys._MEIPASS)
    LEGACY_APP_DIR = Path(sys.executable).resolve().parent
else:
    RESOURCE_DIR = Path(__file__).resolve().parent
    LEGACY_APP_DIR = RESOURCE_DIR

local_appdata = os.environ.get("LOCALAPPDATA")
DATA_DIR = (Path(local_appdata) / "ARSIPTA") if local_appdata else (Path.home() / ".arsipta")
DATA_DIR.mkdir(parents=True, exist_ok=True)

target_db = DATA_DIR / "arsipta_katalog.db"
legacy_db = LEGACY_APP_DIR / "arsipta_katalog.db"
bundled_db = RESOURCE_DIR / "assets" / "data" / "arsipta_katalog.db"

if not target_db.exists():
    if legacy_db.exists() and legacy_db.resolve() != target_db.resolve():
        shutil.copy2(legacy_db, target_db)
    elif bundled_db.exists():
        shutil.copy2(bundled_db, target_db)

os.chdir(DATA_DIR)

from arsipta.runtime import main

if __name__ == "__main__":
    main()
