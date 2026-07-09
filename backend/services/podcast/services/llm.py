from langchain_ollama import ChatOllama
import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:12b")
NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

# Summarization is a faithfulness task: low temperature keeps it close to the source.
summarizer_llm = ChatOllama(
    base_url=OLLAMA_BASE_URL,
    model=OLLAMA_MODEL,
    temperature=0.2,
    num_ctx=NUM_CTX,
)

# Scripting is a storytelling task: warmer temperature is appropriate here only.
scripter_llm = ChatOllama(
    base_url=OLLAMA_BASE_URL,
    model=OLLAMA_MODEL,
    temperature=0.7,
    num_ctx=NUM_CTX,
)

# Rough English ratio (~0.75 words/token). Reserve headroom for prompt scaffolding
# and the model's own output so a single call never silently truncates the input.
_WORDS_PER_TOKEN = 0.75
_RESERVED_TOKENS = 1500
_MAX_INPUT_WORDS = int((NUM_CTX - _RESERVED_TOKENS) * _WORDS_PER_TOKEN)
_CHUNK_WORDS = max(_MAX_INPUT_WORDS // 2, 200)


def _split_into_chunks(text: str, chunk_words: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    return [" ".join(words[i:i + chunk_words]) for i in range(0, len(words), chunk_words)]


async def _summarize_chunk(chunk: str) -> str:
    prompt = (
        "Summarize the following article excerpt for a podcast audience. "
        "Preserve concrete facts, numbers, and names. Do not add information "
        "that isn't in the text:\n\n" + chunk
    )
    response = await summarizer_llm.ainvoke(prompt)
    return response.content


async def generate_summary(text: str) -> str:
    """
    Summarize article content for a podcast audience.

    Long articles are map-reduced (summarize in chunks, then merge) instead of
    sent to the model in one call, because Ollama silently truncates input that
    exceeds the context window rather than raising an error.
    """
    words = text.split()
    if len(words) <= _MAX_INPUT_WORDS:
        return await _summarize_chunk(text)

    chunks = _split_into_chunks(text, _CHUNK_WORDS)
    partial_summaries = [await _summarize_chunk(chunk) for chunk in chunks]

    if len(partial_summaries) == 1:
        return partial_summaries[0]

    merge_prompt = (
        "The following are summaries of consecutive sections of one article, in order. "
        "Merge them into a single coherent summary for a podcast audience, removing "
        "repetition and preserving narrative order and key facts:\n\n"
        + "\n\n".join(f"Section {i + 1}: {s}" for i, s in enumerate(partial_summaries))
    )
    response = await summarizer_llm.ainvoke(merge_prompt)
    return response.content


async def merge_article_summaries(summaries: list[str]) -> str:
    """
    Merge per-article summaries (already in the episode's intended order) into
    one cohesive cross-article briefing summary for the scripter.
    """
    if len(summaries) == 1:
        return summaries[0]

    joined = "\n\n".join(f"Story {i + 1}: {s}" for i, s in enumerate(summaries))
    prompt = (
        "The following are summaries of separate news stories for a single podcast episode, "
        "in the intended order. Merge them into one cohesive briefing: keep each story's key "
        "facts, add natural transitions between stories, and preserve the given order. Do not "
        "blend facts between different stories.\n\n" + joined
    )
    response = await summarizer_llm.ainvoke(prompt)
    return response.content


async def generate_podcast_script(summary: str, target_minutes: float = 3.0) -> str:
    """Generate a conversational podcast script targeting a given spoken duration."""
    target_words = int(target_minutes * 150)  # ~150 spoken words/minute
    prompt = (
        "Convert the following summary into a conversational, engaging podcast narration script. "
        "Use a warm, storytelling tone. "
        f"Target approximately {target_words} words — the script will be read aloud at natural "
        "speaking pace, so length matters. "
        "Output ONLY the spoken narration text: no markdown formatting, no speaker labels, "
        "no headings, no stage directions, and no preamble like 'Here is your script'.\n\n"
        f"Summary: {summary}"
    )
    response = await scripter_llm.ainvoke(prompt)
    return response.content
