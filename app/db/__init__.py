"""Database connection manager with async connection pool."""

import asyncpg
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional, List, Dict
from uuid import UUID

logger = logging.getLogger(__name__)


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Initialize connection with JSON codec for JSONB columns."""
    await conn.set_type_codec(
        'jsonb',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )
    await conn.set_type_codec(
        'json',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )


class Database:
    """Async PostgreSQL database connection manager with connection pooling."""

    def __init__(self, database_url: str, min_size: int = 2, max_size: int = 10):
        """
        Initialize database manager.

        Args:
            database_url: PostgreSQL connection string
            min_size: Minimum pool size
            max_size: Maximum pool size
        """
        self.database_url = database_url
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Create connection pool."""
        if self.pool is not None:
            logger.warning("Database pool already connected")
            return

        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_size,
                max_size=self.max_size,
                command_timeout=60.0,
                init=_init_connection,
            )
            logger.info(
                f"Database pool created (min_size={self.min_size}, max_size={self.max_size})"
            )
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self.pool is None:
            logger.warning("Database pool not connected")
            return

        try:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")
        except Exception as e:
            logger.error(f"Error closing database pool: {e}")
            raise

    async def execute(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None,
    ) -> str:
        """
        Execute a query without returning results.

        Args:
            query: SQL query
            *args: Query parameters
            timeout: Query timeout in seconds

        Returns:
            Query status string (e.g., "INSERT 0 1")
        """
        if self.pool is None:
            raise RuntimeError("Database pool not connected")

        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, *args, timeout=timeout)
                return result
        except Exception as e:
            logger.error(f"Execute error: {e}")
            raise

    async def fetch_one(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a single row.

        Args:
            query: SQL query
            *args: Query parameters
            timeout: Query timeout in seconds

        Returns:
            Dictionary with column names as keys, or None if no row found
        """
        if self.pool is None:
            raise RuntimeError("Database pool not connected")

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, *args, timeout=timeout)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Fetch one error: {e}")
            raise

    async def fetch_all(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all rows.

        Args:
            query: SQL query
            *args: Query parameters
            timeout: Query timeout in seconds

        Returns:
            List of dictionaries with column names as keys
        """
        if self.pool is None:
            raise RuntimeError("Database pool not connected")

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *args, timeout=timeout)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Fetch all error: {e}")
            raise

    async def fetch_val(
        self,
        query: str,
        *args,
        column: int = 0,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Fetch a single value.

        Args:
            query: SQL query
            *args: Query parameters
            column: Column index to return
            timeout: Query timeout in seconds

        Returns:
            Single value from the first row and specified column
        """
        if self.pool is None:
            raise RuntimeError("Database pool not connected")

        try:
            async with self.pool.acquire() as conn:
                value = await conn.fetchval(query, *args, column=column, timeout=timeout)
                return value
        except Exception as e:
            logger.error(f"Fetch val error: {e}")
            raise

    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for database transactions.

        Example:
            async with db.transaction() as conn:
                await conn.execute("INSERT INTO ...")
                await conn.execute("UPDATE ...")
        """
        if self.pool is None:
            raise RuntimeError("Database pool not connected")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """
    Dependency injection function for database access.

    Returns:
        Database instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


def init_db(database_url: str, min_size: int = 2, max_size: int = 10) -> Database:
    """
    Initialize global database instance.

    Args:
        database_url: PostgreSQL connection string
        min_size: Minimum pool size
        max_size: Maximum pool size

    Returns:
        Database instance
    """
    global _db
    _db = Database(database_url, min_size, max_size)
    return _db


async def close_db() -> None:
    """Close global database instance."""
    global _db
    if _db is not None:
        await _db.disconnect()
        _db = None


__all__ = ["Database", "get_db", "init_db", "close_db"]
