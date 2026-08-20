from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.database import get_engine


async def main() -> None:
    engine = get_engine()

    async with engine.begin() as conn:
        dialect = conn.dialect.name

        if dialect == "mysql":
            exists = await conn.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'user'
                      AND COLUMN_NAME = 'password_hash'
                    """
                )
            )
            if not exists:
                await conn.execute(
                    text(
                        "ALTER TABLE `user` "
                        "ADD COLUMN password_hash VARCHAR(255) NULL AFTER nickname"
                    )
                )
                print("Added user.password_hash column.")
            else:
                print("user.password_hash already exists. Nothing to do.")

        elif dialect == "sqlite":
            rows = (await conn.execute(text("PRAGMA table_info('user')"))).all()
            column_names = {row[1] for row in rows}
            if "password_hash" not in column_names:
                await conn.execute(text("ALTER TABLE user ADD COLUMN password_hash VARCHAR(255) NULL"))
                print("Added user.password_hash column.")
            else:
                print("user.password_hash already exists. Nothing to do.")
        else:
            raise RuntimeError(f"Unsupported database dialect for this migration: {dialect}")


if __name__ == "__main__":
    asyncio.run(main())
