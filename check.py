import importlib
import traceback

MODULES = [
    "app.models",
    "app.models.message",
    "app.schemas.message",
    "app.ws",
    "app.routers.message",
    "app.routers.live",
    "app.routers.user",
    "app.main",
]

print("=== 1. Imports ===")
for name in MODULES:
    try:
        importlib.import_module(name)
        print("OK     ", name)
    except Exception:
        print("FAILED ", name)
        traceback.print_exc()

print("\n=== 2. Message routes registered in app.main ===")
try:
    from app.main import app

    paths = sorted({r.path for r in app.routes})
    shown = [p for p in paths if p.startswith("/messages") or p == "/ws"]
    print("\n".join(shown) if shown else "(none)")
    if not any(p.startswith("/messages") for p in paths):
        print("PROBLEM: app/main.py does not include the messages router")
except Exception:
    traceback.print_exc()

print("\n=== 3. Database ===")
try:
    from sqlalchemy import inspect, text
    from app.database import engine

    with engine.connect() as conn:
        print("users in database:", conn.execute(text("SELECT count(*) FROM users")).scalar())

    inspector = inspect(engine)
    if "messages" not in inspector.get_table_names():
        print("PROBLEM: messages table does not exist")
    else:
        columns = [c["name"] for c in inspector.get_columns("messages")]
        print("messages columns:", columns)
        if "kind" not in columns:
            print("PROBLEM: messages table has no 'kind' column, so run the reset script")
except Exception:
    traceback.print_exc()