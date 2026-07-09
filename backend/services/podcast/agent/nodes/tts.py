from ..state import EpisodeState
from ...services.tts import tts_service, TTSAssetsMissing
from ...services.status import publish_status

async def tts_node(state: EpisodeState) -> dict:
    """Synthesize the script to audio."""
    if state.get("error"):
        return {}

    episode_id = state["episode_id"]
    print(f"Synthesizing audio for episode {episode_id}...")
    temp_wav_path = f"/tmp/{episode_id}.wav"

    async def on_progress(done: int, total: int) -> None:
        await publish_status(episode_id, "synthesizing", progress=int(done / total * 100))

    try:
        voice = state.get("voice", "af_heart")
        success = await tts_service.synthesize(
            state["podcast_script"], temp_wav_path, voice=voice, on_progress=on_progress
        )
        if success:
            return {"audio_path": temp_wav_path, "status": "saving"}
        else:
            return {"status": "error", "error": "TTS synthesis failed"}
    except TTSAssetsMissing as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"TTS node failed: {str(e)}"}
