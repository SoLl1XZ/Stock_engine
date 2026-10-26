from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
CACHE_DIR: Path = DATA_DIR / "cache"
SITE_DIR: Path = ROOT / "site"
SITE_DATA_DIR: Path = SITE_DIR / "data"

# SEC requires a descriptive User-Agent on every request.
SEC_USER_AGENT: str = "Stock Engine 222303744+SoLl1XZ@users.noreply.github.com"
