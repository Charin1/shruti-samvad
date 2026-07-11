from langchain_ollama import ChatOllama
import os
from typing import Optional

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


async def generate_podcast_script(
    summary: str,
    target_minutes: float = 3.0,
    podcast_style: str = "conversational",
    custom_prompt: Optional[str] = None
) -> str:
    """Generate a podcast script targeting a given spoken duration with custom style and self-correcting loop engineering."""
    from typing import Optional
    target_words = int(target_minutes * 150)  # ~150 spoken words/minute

    style_prompts = {
        "conversational": "Use a warm, storytelling, and conversational tone, like a friendly podcast host explaining things to a friend.",
        "briefing": "Use a concise, professional news briefing tone. Keep it direct, clear, and fast-paced.",
        "analytical": "Use an analytical, deep-dive tone. Focus on explanations, implications, and context, like an expert essayist.",
        "dramatic": "Use a dramatic, high-energy storytelling tone. Build suspense, emphasize key moments, and make it sound theatrical.",
        "humorous": "Use a lighthearted, witty, and slightly humorous tone. Use clever analogies and casual, entertaining wording."
    }

    selected_style_instruction = style_prompts.get(podcast_style, style_prompts["conversational"])

    prompt = (
        "Convert the following summary into a spoken podcast narration script.\n"
        f"Tone and Style instruction: {selected_style_instruction}\n"
    )

    if custom_prompt and custom_prompt.strip():
        prompt += f"Additional Custom Instructions: {custom_prompt.strip()}\n"

    prompt += (
        f"Target length: approximately {target_words} words (will be read aloud at normal speaking pace, so word count matters).\n"
        "Constraint: Output ONLY the spoken narration text: no markdown formatting, no speaker labels, "
        "no headings, no stage directions, and no preamble like 'Here is your script'.\n\n"
        f"Summary: {summary}"
    )

    print(f"[Loop Eng] Generating initial script (target: {target_words} words, style: {podcast_style})...")
    response = await scripter_llm.ainvoke(prompt)
    script = response.content

    # Self-Correction / Loop Engineering Loop
    max_attempts = 3  # Initial + 2 refinement attempts
    for attempt in range(1, max_attempts):
        words = script.split()
        word_count = len(words)
        
        reasons = []
        
        # 1. Word count constraint check (allow ±25% margin or 75 words, whichever is larger)
        margin = max(int(target_words * 0.25), 75)
        min_w = max(30, target_words - margin)
        max_w = target_words + margin
        
        if word_count < min_w or word_count > max_w:
            reasons.append(f"Word count is {word_count}, but the target is {target_words} words (acceptable range: {min_w} to {max_w} words).")
            
        # 2. Format constraint check: look for speaker labels or markdown formatting
        import re
        has_speaker_labels = bool(re.search(r'^\s*(?:\[[^\]]+\]|\([^)]+\))\s*:?\s*|^\s*[A-Z][A-Za-z0-9 ]{0,20}:\s*', script, re.MULTILINE))
        has_markdown = bool(re.search(r'(\*\*|\*|#)', script))
        
        if has_speaker_labels:
            reasons.append("The script contains speaker labels (like 'Host:', '[Host]', 'Speaker 1:').")
        if has_markdown:
            reasons.append("The script contains markdown styling (like headings, asterisks, or bold text).")
            
        if not reasons:
            print(f"[Loop Eng] Script passed all checks on attempt {attempt}!")
            break
            
        feedback_msg = "\n".join(f"- {r}" for r in reasons)
        print(f"[Loop Eng] Attempt {attempt} failed constraints:\n{feedback_msg}\nRefining...")
        
        refine_prompt = (
            "You are a podcast script editor. The script you generated previously does not meet the requirements.\n\n"
            f"Here is the script you generated:\n---\n{script}\n---\n\n"
            "Please revise the script to fix the following issues:\n"
            f"{feedback_msg}\n\n"
            f"Style & Tone constraint: {selected_style_instruction}\n"
            f"Target length: {target_words} words.\n"
            "Output ONLY the final revised spoken narration text. No markdown, no headings, no speaker labels, no preamble, and no stage directions."
        )
        
        response = await scripter_llm.ainvoke(refine_prompt)
        script = response.content

    return script
