import operator
from typing import Annotated, Optional, TypedDict


class ArticleInput(TypedDict):
    article_id: str
    clean_text: str
    position: int


class ArticleSummary(TypedDict):
    article_id: str
    position: int
    summary: Optional[str]
    error: Optional[str]  # set instead of raising, so concurrent Send branches
    # never race-write the top-level `status`/`error` keys (which have no
    # reducer) — merge_summaries_node inspects this list and is the only node
    # that sets the singular status/error fields for a failure.


class EpisodeState(TypedDict):
    episode_id: str
    target_minutes: float
    review_requested: bool
    voice: str  # TTS voice selection (e.g., "af_heart", "af_sky")
    voice_cohost: str  # Co-host voice selection
    podcast_format: str  # monologue or dialogue
    podcast_style: str  # style/tone for podcast script
    custom_prompt: Optional[str]  # user custom prompt/instructions
    bg_music: bool  # play background music
    articles: list[ArticleInput]  # loaded once by the worker before invoke
    # Reducer concatenates each summarize_one fan-out branch's result — branches
    # may complete out of order, so each entry carries its own `position`.
    article_summaries: Annotated[list[ArticleSummary], operator.add]
    summary: str  # merged cross-article summary (reduce output)
    podcast_script: str
    audio_path: Optional[str]
    status: str
    error: Optional[str]
