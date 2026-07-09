import asyncio
import os

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from .state import EpisodeState
from .nodes.summarizer import summarize_one_node
from .nodes.merge_summaries import merge_summaries_node
from .nodes.scripter import scripter_node
from .nodes.review_gate import review_gate_node
from .nodes.tts import tts_node
from .nodes.saver import saver_node

CHECKPOINT_DB_PATH = os.getenv("CHECKPOINT_DB_PATH", "./storage/checkpoints/episodes.sqlite")


def _fan_out_summaries(state: EpisodeState) -> list[Send]:
    return [Send("summarize_one", article) for article in state["articles"]]


def _after_script(state: EpisodeState) -> str:
    if state.get("error"):
        return END
    return "review_gate" if state.get("review_requested") else "tts"


def build_episode_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """Build and compile the LangGraph StateGraph for episode generation.

    Shape: fan out to summarize each article in parallel (Send API) -> join
    at merge_summaries -> script -> optional human review gate (interrupt)
    -> tts -> save. `interrupt_after=["review_gate"]` pauses the graph right
    after that node runs, whenever the "review_requested" branch is taken —
    the checkpointer persists state so a later call can resume past it.
    """
    workflow = StateGraph(EpisodeState)

    workflow.add_node("summarize_one", summarize_one_node)
    workflow.add_node("merge_summaries", merge_summaries_node)
    workflow.add_node("script", scripter_node)
    workflow.add_node("review_gate", review_gate_node)
    workflow.add_node("tts", tts_node)
    workflow.add_node("save", saver_node)

    workflow.add_conditional_edges(START, _fan_out_summaries, ["summarize_one"])
    workflow.add_edge("summarize_one", "merge_summaries")
    workflow.add_edge("merge_summaries", "script")
    workflow.add_conditional_edges("script", _after_script, ["review_gate", "tts", END])
    workflow.add_edge("review_gate", "tts")
    workflow.add_edge("tts", "save")
    workflow.add_edge("save", END)

    return workflow.compile(checkpointer=checkpointer, interrupt_after=["review_gate"])


_graph = None
_checkpointer_cm = None
_graph_lock = asyncio.Lock()


async def get_episode_graph():
    """
    Cached async singleton (mirrors the get_arq_pool() pattern used elsewhere
    in this codebase) — AsyncSqliteSaver must be entered via an async context
    manager, so the compiled graph can't be a plain module-level constant.
    """
    global _graph, _checkpointer_cm
    if _graph is not None:
        return _graph

    async with _graph_lock:
        if _graph is None:
            os.makedirs(os.path.dirname(CHECKPOINT_DB_PATH), exist_ok=True)
            _checkpointer_cm = AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH)
            checkpointer = await _checkpointer_cm.__aenter__()
            _graph = build_episode_graph(checkpointer)
    return _graph
