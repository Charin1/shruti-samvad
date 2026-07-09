from ..state import EpisodeState
from ...services.llm import generate_podcast_script
from ...services.sanitizer import sanitize_script, validate_script

async def scripter_node(state: EpisodeState) -> dict:
    """Generate a conversational podcast script."""
    if state.get("error"):
        return {}

    print(f"Generating script for episode {state['episode_id']}...")
    try:
        raw_script = await generate_podcast_script(
            state["summary"], target_minutes=state.get("target_minutes", 3.0)
        )
        script = sanitize_script(raw_script)
        validation_error = validate_script(script)
        if validation_error:
            return {"status": "error", "error": validation_error}
        # Announce the status of whichever branch runs next (review_gate or
        # tts) — LangGraph streams per-node, so this is the last chance to
        # signal "about to review/synthesize" before that node executes.
        next_status = "awaiting_review" if state.get("review_requested") else "synthesizing"
        return {"podcast_script": script, "status": next_status}
    except Exception as e:
        return {"status": "error", "error": f"Scripting failed: {str(e)}"}
