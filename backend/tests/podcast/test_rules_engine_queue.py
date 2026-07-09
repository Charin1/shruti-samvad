"""
Tests that rules engine enqueues podcast jobs to the correct queue.

Bug: rules_engine.py had _queue_name='podcast_queue' (wrong) instead of 'arq:podcast'.
The RSS worker would then steal the job since it wasn't in the podcast queue.
"""
import inspect
from services.rss.logic.rules_engine import execute_rule_action


def test_rules_engine_uses_correct_podcast_queue():
    """The literal queue name 'arq:podcast' must appear in execute_rule_action source."""
    source = inspect.getsource(execute_rule_action)
    assert "arq:podcast" in source, (
        "execute_rule_action must enqueue to 'arq:podcast', not 'podcast_queue' or default queue"
    )
    assert "podcast_queue" not in source, (
        "Old wrong queue name 'podcast_queue' found — change to 'arq:podcast'"
    )
