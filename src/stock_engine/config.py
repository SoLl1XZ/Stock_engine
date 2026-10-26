import os
from pathlib import Path

from dotenv import load_dotenv

ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
CACHE_DIR: Path = DATA_DIR / "cache"
SITE_DIR: Path = ROOT / "site"
SITE_DATA_DIR: Path = SITE_DIR / "data"



def sec_user_agent() -> str:
    # SEC Fair Access requires a declared contact; override=False lets a real env var (Actions secret) win over .env.
    load_dotenv(ROOT / ".env", override=False)
    email = os.environ.get("SEC_CONTACT_EMAIL", "").strip()
    if not email:
        raise RuntimeError(
            "SEC_CONTACT_EMAIL is not set. Put it in .env (see .env.example) "
            "or add it as a GitHub Actions secret."
        )
    return f"Stock Engine {email}"
