"""
Tests for podcast worker configuration.

Covers the queue collision bug: RSS worker was stealing podcast jobs
because both used the default arq queue name.
"""
from services.podcast.worker import WorkerSettings, PODCAST_QUEUE


def test_podcast_worker_uses_dedicated_queue():
    assert WorkerSettings.queue_name == "arq:podcast"
    assert WorkerSettings.queue_name != "arq:queue"  # must NOT use default RSS queue


def test_podcast_queue_constant_matches_worker_settings():
    assert PODCAST_QUEUE == WorkerSettings.queue_name


def test_podcast_queue_name_value():
    assert PODCAST_QUEUE == "arq:podcast"
