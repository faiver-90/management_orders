import asyncio
import os
import subprocess
import sys
import time

import asyncpg

host = os.getenv("POSTGRES_HOST", "postgres")
port = int(os.getenv("POSTGRES_PORT", "5432"))
db = os.getenv("POSTGRES_DB", "orders")
user = os.getenv("POSTGRES_USER", "orders")
pw = os.getenv("POSTGRES_PASSWORD", "orders")

dsn = f"postgresql://{user}:{pw}@{host}:{port}/{db}"


async def main() -> None:
    deadline = time.time() + 60
    last: Exception | None = None

    while time.time() < deadline:
        try:
            conn = await asyncpg.connect(dsn)
            await conn.close()
            print("Postgres is ready")
            break
        except Exception as e:
            last = e
            await asyncio.sleep(1)
    else:
        print("Postgres not ready:", repr(last))
        sys.exit(1)

    print("Running alembic migrations")
    subprocess.run(["alembic", "upgrade", "head"], check=True)


asyncio.run(main())
