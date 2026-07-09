from services.podcast.services.estimator import estimate_progress, STAGE_ORDER


def test_progress_zero_at_start_of_first_stage():
    progress, eta = estimate_progress("summarizing", elapsed_in_stage=0, article_count=1, target_minutes=3.0)
    assert progress == 0
    assert eta > 0


def test_progress_increases_with_elapsed_time_within_a_stage():
    p1, eta1 = estimate_progress("summarizing", elapsed_in_stage=10, article_count=1, target_minutes=3.0)
    p2, eta2 = estimate_progress("summarizing", elapsed_in_stage=100, article_count=1, target_minutes=3.0)
    assert p2 > p1
    assert eta2 < eta1


def test_progress_accounts_for_completed_earlier_stages():
    """Being in 'scripting' should already show more progress than being at
    the very start of 'summarizing', even with zero elapsed time in-stage."""
    p_summarize, _ = estimate_progress("summarizing", elapsed_in_stage=0, article_count=1, target_minutes=3.0)
    p_script, _ = estimate_progress("scripting", elapsed_in_stage=0, article_count=1, target_minutes=3.0)
    assert p_script > p_summarize


def test_progress_never_reaches_100_from_the_estimate_alone():
    """Reserved for the real terminal 'done' status — avoids a bar that reads
    100% while the episode is still technically in progress."""
    progress, eta = estimate_progress("saving", elapsed_in_stage=10_000, article_count=1, target_minutes=3.0)
    assert progress == 99
    assert eta == 0


def test_more_articles_increases_total_estimate_and_thus_lowers_progress_for_same_elapsed_time():
    p_one, _ = estimate_progress("summarizing", elapsed_in_stage=60, article_count=1, target_minutes=3.0)
    p_many, _ = estimate_progress("summarizing", elapsed_in_stage=60, article_count=5, target_minutes=3.0)
    assert p_many < p_one


def test_unknown_status_returns_zero_progress():
    progress, eta = estimate_progress("awaiting_review", elapsed_in_stage=0, article_count=1, target_minutes=3.0)
    assert progress == 0
    assert eta > 0


def test_stage_order_matches_pipeline_sequence():
    assert STAGE_ORDER == ["summarizing", "scripting", "synthesizing", "saving"]
