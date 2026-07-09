import os
from arq import create_pool
from arq.connections import RedisSettings

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_pool = None


async def get_arq_pool():
    """Return a cached arq Redis pool for enqueuing background jobs."""
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    return _pool
