from ..state import EpisodeState
from ...services.llm import merge_article_summaries


async def merge_summaries_node(state: EpisodeState) -> dict:
    """
    Join point after the summarize_one fan-out. Runs once (not fanned), so
    this is the first safe place to set the singular `status`/`error` keys —
    checks for any per-article failure first, then merges the (order-restored)
    successful summaries into one cross-article briefing.
    """
    failed = [s for s in state["article_summaries"] if s.get("error")]
    if failed:
        return {"status": "error", "error": failed[0]["error"]}

    ordered = sorted(state["article_summaries"], key=lambda s: s["position"])
    summaries = [s["summary"] for s in ordered]

    print(f"Merging {len(summaries)} article summaries for episode {state['episode_id']}...")
    try:
        merged = await merge_article_summaries(summaries)
        return {"summary": merged, "status": "scripting"}
    except Exception as e:
        return {"status": "error", "error": f"Merging summaries failed: {str(e)}"}
