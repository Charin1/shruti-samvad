import os

# Stages the estimator can position within (excludes terminal/paused states —
# callers handle "done"/"error"/"awaiting_review" separately).
STAGE_ORDER = ["summarizing", "scripting", "synthesizing", "saving"]

# Rough per-stage duration constants, tunable via env vars since local LLM/TTS
# throughput varies a lot by hardware and by what else is competing for RAM.
# Defaults are ballpark figures observed on a memory-constrained M-series Mac
# running Gemma 12B Q4 — they only drive a progress estimate, not correctness.
SECONDS_PER_ARTICLE_SUMMARIZE = float(os.getenv("EST_SECONDS_PER_ARTICLE_SUMMARIZE", "240"))
SECONDS_SCRIPT = float(os.getenv("EST_SECONDS_SCRIPT", "200"))
SECONDS_PER_TTS_MINUTE = float(os.getenv("EST_SECONDS_PER_TTS_MINUTE", "40"))
SECONDS_SAVE = float(os.getenv("EST_SECONDS_SAVE", "10"))


def _stage_estimates(article_count: int, target_minutes: float) -> dict[str, float]:
    return {
        "summarizing": SECONDS_PER_ARTICLE_SUMMARIZE * max(article_count, 1),
        "scripting": SECONDS_SCRIPT,
        "synthesizing": SECONDS_PER_TTS_MINUTE * max(target_minutes, 0.5),
        "saving": SECONDS_SAVE,
    }


def estimate_progress(
    status: str,
    elapsed_in_stage: float,
    article_count: int,
    target_minutes: float,
) -> tuple[int, int]:
    """
    Returns (progress_percent capped at 99, eta_seconds_remaining) for a
    status in STAGE_ORDER, given how long the pipeline has been in that
    stage. Capped below 100 so the bar never claims "done" before the
    episode's status actually reaches "done". Callers should special-case
    terminal states (done -> 100/0) rather than calling this for them.
    """
    estimates = _stage_estimates(article_count, target_minutes)
    total = sum(estimates.values())

    if status not in STAGE_ORDER or total <= 0:
        return 0, int(total)

    completed = sum(estimates[s] for s in STAGE_ORDER[: STAGE_ORDER.index(status)])
    current_estimate = estimates[status]
    stage_fraction = min(elapsed_in_stage / current_estimate, 1.0) if current_estimate > 0 else 1.0

    elapsed_total = completed + stage_fraction * current_estimate
    progress_pct = min(int(elapsed_total / total * 100), 99)
    eta_seconds = max(int(total - elapsed_total), 0)
    return progress_pct, eta_seconds
