from ..state import ArticleInput
from ...services.llm import generate_summary


async def summarize_one_node(state: ArticleInput) -> dict:
    """
    Summarize a single article. Invoked once per article via LangGraph's Send
    fan-out — `state` here is just that one article's payload, not the full
    EpisodeState. Returns a list-wrapped result so the `article_summaries`
    reducer (operator.add) can concatenate results from parallel branches,
    which may complete in any order.
    """
    article_id = state["article_id"]
    position = state["position"]
    print(f"Summarizing article {article_id} (position {position})...")
    try:
        summary = await generate_summary(state["clean_text"])
        return {
            "article_summaries": [
                {"article_id": article_id, "position": position, "summary": summary, "error": None}
            ]
        }
    except Exception as e:
        # Recorded per-article rather than raised/set on the top-level `status`/
        # `error` keys, since those have no reducer and would conflict if two
        # fanned-out branches failed in the same superstep.
        return {
            "article_summaries": [
                {
                    "article_id": article_id,
                    "position": position,
                    "summary": None,
                    "error": f"Summarization failed for article {article_id}: {str(e)}",
                }
            ]
        }
