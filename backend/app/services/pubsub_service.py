import json
import logging
import redis
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)


def publish_scan_event_sync(scan_id: str, event_type: str, data: dict) -> None:
    """Publish event from Celery worker (synchronous)."""
    client = redis.Redis.from_url(settings.redis_url)
    try:
        payload = json.dumps({"type": event_type, "data": data})
        client.publish(f"scan:{scan_id}:events", payload)
    finally:
        client.close()


async def subscribe_scan_events(scan_id: str):
    """Async generator yielding events for a scan. Used by WebSocket handler."""
    client = aioredis.from_url(settings.redis_url)
    pubsub = client.pubsub()
    await pubsub.subscribe(f"scan:{scan_id}:events")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    event = json.loads(message["data"])
                    yield event
                except json.JSONDecodeError:
                    continue
    finally:
        await pubsub.unsubscribe(f"scan:{scan_id}:events")
        await pubsub.close()
        await client.close()
