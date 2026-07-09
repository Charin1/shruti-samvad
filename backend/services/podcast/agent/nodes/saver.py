import os
from pydub import AudioSegment
from ..state import EpisodeState

async def saver_node(state: EpisodeState) -> dict:
    """Convert WAV to MP3 and move to persistent storage."""
    if state.get("error"):
        return {}

    print(f"Saving final audio for episode {state['episode_id']}...")

    if not state.get("audio_path") or not os.path.exists(state["audio_path"]):
        return {
            "status": "error",
            "error": "Temporary audio file not found"
        }

    storage_path = os.getenv("AUDIO_STORAGE_PATH", "./storage/audio")
    os.makedirs(storage_path, exist_ok=True)
    final_mp3_path = os.path.join(storage_path, f"{state['episode_id']}.mp3")
    
    try:
        # Convert WAV to MP3 using pydub
        # Note: Requires ffmpeg
        audio = AudioSegment.from_wav(state["audio_path"])
        audio.export(final_mp3_path, format="mp3", bitrate="128k")
        os.remove(state["audio_path"])
        
        return {
            "audio_path": final_mp3_path,
            "status": "done"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Audio saving/conversion failed: {str(e)}"
        }
