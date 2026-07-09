from arq.connections import RedisSettings
import os

from services.rss.workers.feed_fetcher import fetch_feed_task
from services.rss.workers.content_extractor import extract_content_task
from services.rss.logic.rules_engine import evaluate_rules_for_article

# Tasks
async def run_rules_task(ctx, article_id):
    return await evaluate_rules_for_article(ctx, article_id)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class WorkerSettings:
    """Settings for the arq worker."""
    functions = [
        fetch_feed_task,
        extract_content_task,
        run_rules_task
    ]
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    
    # Optionally define cron jobs here
    # cron_jobs = [
    #     cron(refresh_all_feeds, minute=0)
    # ]

async def startup(ctx):
    print("RSS Ingestion Worker started")

async def shutdown(ctx):
    print("RSS Ingestion Worker shutting down")

if __name__ == "__main__":
    # This allows running with `python worker.py` for testing
    from arq import run_worker
    run_worker(WorkerSettings)
