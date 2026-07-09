from ..state import EpisodeState


async def review_gate_node(state: EpisodeState) -> dict:
    """
    No-op passthrough. Its only purpose is to exist as a named node so
    `interrupt_after=["review_gate"]` has a target — the graph checkpoints
    state and pauses right after this node runs. `scripter_node` already set
    status to "awaiting_review" before this node was reached, so there's
    nothing left to do here.
    """
    return {}
