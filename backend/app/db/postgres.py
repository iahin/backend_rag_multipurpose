from psycopg import OperationalError
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import Settings
from app.models.schemas import DependencyHealth


class PostgresManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool = AsyncConnectionPool(
            conninfo=settings.postgres_dsn,
            min_size=settings.postgres_min_pool_size,
            max_size=settings.postgres_max_pool_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    @property
    def pool(self) -> AsyncConnectionPool:
        return self._pool

    async def connect(self) -> None:
        await self._pool.open()

    async def close(self) -> None:
        await self._pool.close()

    async def healthcheck(self) -> DependencyHealth:
        try:
            async with self._pool.connection() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute("SELECT 1 AS ok;")
                    row = await cursor.fetchone()
            return DependencyHealth(ok=bool(row and row["ok"] == 1), detail="connected")
        except OperationalError as exc:
            return DependencyHealth(ok=False, detail=f"postgres_unreachable: {exc}")
        except Exception as exc:  # pragma: no cover - defensive branch
            return DependencyHealth(ok=False, detail=f"postgres_error: {exc}")
