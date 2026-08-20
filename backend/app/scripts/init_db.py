import asyncio

from app.core.database import create_tables


async def main() -> None:
    await create_tables()
    print("Database tables created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
