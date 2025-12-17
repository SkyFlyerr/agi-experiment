"""
Database module for Server Agent vNext
Provides async database connection and query utilities
"""

import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Pool, Connection

from app.config import settings

logger = logging.getLogger(__name__)


class Database:
    """Database connection manager"""

    def __init__(self):
        self.pool: Optional[Pool] = None

    async def connect(self):
        """Establish database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise

    async def disconnect(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")

    async def execute(self, query: str, *args) -> str:
        """Execute a query without returning results"""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch multiple rows"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def fetch_val(self, query: str, *args) -> Any:
        """Fetch a single value"""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    @asynccontextmanager
    async def transaction(self):
        """Context manager for transactions"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn


# Global database instance
_db_instance: Optional[Database] = None


async def get_db() -> Database:
    """Dependency injection for database"""
    global _db_instance
    if not _db_instance:
        _db_instance = Database()
        await _db_instance.connect()
    return _db_instance
