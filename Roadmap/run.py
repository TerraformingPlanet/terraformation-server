"""
Roadmap Service — local launcher (no Docker required).

Usage:
    python run.py                  # default: 127.0.0.1:8001
    PORT=8002 python run.py        # custom port
    DB_PATH=./my.db python run.py  # custom DB location

The DB is created automatically on first run next to this file (roadmap.db).
Seed initial data from Documentation/roadmap.json:
    python migrate.py
"""
import os
import uvicorn

PORT = int(os.environ.get("PORT", "8001"))

if __name__ == "__main__":
    uvicorn.run(
        "app.server:app",
        host="127.0.0.1",
        port=PORT,
        reload=False,
        log_level="info",
    )
