import json
import os
import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_redis = None


async def _get_redis():
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def publish_status(job_id: str, status: str, **extra) -> None:
    """
    Publish a job status update on the `job_status_{job_id}` channel that
    main.py's redis_listener bridges to WebSocket subscribers.

    Used for updates that happen *inside* a single LangGraph node (e.g. TTS
    synthesis progress), which the worker's own per-node `_publish` call
    can't report since it only fires between node transitions.
    """
    redis = await _get_redis()
    payload = json.dumps({"job_id": job_id, "status": status, **extra})
    await redis.publish(f"job_status_{job_id}", payload)
