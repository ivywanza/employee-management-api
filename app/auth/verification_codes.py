import hashlib
import hmac
import os
import secrets
import threading
import time

from dotenv import load_dotenv

load_dotenv()

CODE_TTL_SECONDS = 10 * 60
MAX_ATTEMPTS = 5

_SECRET = (os.getenv("SECRET_KEY") or "").encode()
_codes: dict[tuple[str, str], dict] = {}
_lock = threading.Lock()


def _digest(code: str) -> str:
    return hmac.new(_SECRET, code.encode(), hashlib.sha256).hexdigest()


def _purge_expired() -> None:
    now = time.time()
    for key in [k for k, v in _codes.items() if v["expires_at"] < now]:
        del _codes[key]


def create_code(user_id, purpose: str) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    with _lock:
        _purge_expired()
        # Same user + purpose overwrites the old code, so asking for a new one cancels the previous
        _codes[(str(user_id), purpose)] = {
            "digest": _digest(code),
            "expires_at": time.time() + CODE_TTL_SECONDS,
            "attempts": 0,
        }
    return code


def check_code(user_id, purpose: str, code: str) -> bool:
    key = (str(user_id), purpose)
    with _lock:
        entry = _codes.get(key)
        if entry is None:
            return False
        if entry["expires_at"] < time.time() or entry["attempts"] >= MAX_ATTEMPTS:
            del _codes[key]
            return False

        entry["attempts"] += 1
        if hmac.compare_digest(entry["digest"], _digest(code)):
            del _codes[key]  # a code works only once
            return True
        return False