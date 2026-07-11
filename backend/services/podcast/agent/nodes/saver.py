import os
from pydub import AudioSegment
from ..state import EpisodeState

def find_asset(directory, name):
    for ext in [".mp3", ".wav", ".ogg", ".m4a"]:
        path = os.path.join(directory, f"{name}{ext}")
        if os.path.exists(path):
            return path
    return None

async def saver_node(state: EpisodeState) -> dict:
    """Convert WAV to MP3, optionally mix background music/jingles, and move to persistent storage."""
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
    
    # Resolve assets directory for background music & jingles
    assets_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), "../../../../assets/audio"))
    if not os.path.exists(assets_dir):
        assets_dir = os.path.join(os.getcwd(), "backend/assets/audio")
    os.makedirs(assets_dir, exist_ok=True)
    
    try:
        # Load core voice track
        audio = AudioSegment.from_wav(state["audio_path"])
        
        bg_music_enabled = state.get("bg_music", False)
        if bg_music_enabled:
            bg_file = find_asset(assets_dir, "background")
            intro_file = find_asset(assets_dir, "intro")
            outro_file = find_asset(assets_dir, "outro")
            
            # 1. Overlay background music bed
            if bg_file:
                try:
                    bg = AudioSegment.from_file(bg_file)
                    # Loop bg music if it is shorter than voice track, otherwise trim
                    if len(bg) < len(audio):
                        loops = (len(audio) // len(bg)) + 1
                        bg = bg * loops
                    bg = bg[:len(audio)]
                    # Duck bg music by 20dB
                    bg = bg - 20
                    # Overlay
                    audio = audio.overlay(bg)
                    print(f"Successfully mixed background music bed: {bg_file}")
                except Exception as e:
                    print(f"Warning: Failed to mix background music: {e}")
            else:
                print("Background music requested but no 'background' audio asset found. Skipping music bed.")

            # 2. Concat Intro / Outro jingles
            if intro_file or outro_file:
                combined = AudioSegment.empty()
                
                # Prepend Intro
                if intro_file:
                    try:
                        intro = AudioSegment.from_file(intro_file)
                        combined += intro
                        print(f"Successfully prepended intro jingle: {intro_file}")
                    except Exception as e:
                        print(f"Warning: Failed to prepend intro: {e}")
                        
                combined += audio
                
                # Append Outro
                if outro_file:
                    try:
                        outro = AudioSegment.from_file(outro_file)
                        combined += outro
                        print(f"Successfully appended outro jingle: {outro_file}")
                    except Exception as e:
                        print(f"Warning: Failed to append outro: {e}")
                        
                audio = combined

        # Export final MP3
        audio.export(final_mp3_path, format="mp3", bitrate="128k")
        
        if os.path.exists(state["audio_path"]):
            os.remove(state["audio_path"])
        
        return {
            "audio_path": final_mp3_path,
            "status": "done"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Audio saving/conversion/mixing failed: {str(e)}"
        }
