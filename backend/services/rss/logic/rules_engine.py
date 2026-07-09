from sqlmodel import select
from typing import List
from uuid import UUID

from core.database.session import async_session_maker
from core.database.models.rule import Rule
from core.database.models.article import Article, ArticleSave, ArticleStar
from core.database.models.episode import Episode, EpisodeArticle

async def evaluate_rules_for_article(ctx, article_id: UUID):
    """
    Evaluate all active rules for a given article and execute actions.
    """
    async with async_session_maker() as session:
        article = await session.get(Article, article_id)
        if not article:
            return f"Article {article_id} not found"
            
        # Get all active rules
        # Note: In a real multi-user system, we'd filter by the owner of the feed/article mapping
        query = select(Rule).where(Rule.is_active == True)
        result = await session.execute(query)
        rules = result.scalars().all()
        
        matches = []
        for rule in rules:
            matched = False
            
            # Simple keyword matching for now
            if rule.condition_type == "keyword":
                if rule.condition_value.lower() in article.title.lower() or \
                   (article.clean_text and rule.condition_value.lower() in article.clean_text.lower()):
                    matched = True
            
            # TODO: add more condition types (source, etc.)
            
            if matched:
                matches.append(rule.name)
                await execute_rule_action(ctx, session, article, rule)
                
        await session.commit()
        
    return f"Processed rules for {article.title}. Matches: {', '.join(matches) if matches else 'None'}"

async def execute_rule_action(ctx, session, article, rule):
    """Execute the action defined in a rule."""
    if rule.action == "save":
        save = ArticleSave(user_id=rule.user_id, article_id=article.id)
        session.add(save)
    elif rule.action == "star":
        star = ArticleStar(user_id=rule.user_id, article_id=article.id)
        session.add(star)
    elif rule.action == "podcast":
        episode = Episode(title=article.title)
        session.add(episode)
        await session.flush()  # assign episode.id
        session.add(EpisodeArticle(episode_id=episode.id, article_id=article.id, position=0))
        # Commit before enqueuing — the podcast worker reads this episode via
        # its own DB connection and would race an uncommitted transaction.
        await session.commit()
        await ctx['redis'].enqueue_job('process_episode_job', episode.id, _queue_name='arq:podcast')
    elif rule.action == "mute":
        article.is_duplicate = True # Using duplicate as a proxy for hidden/muted for now
        session.add(article)
    # TODO: implement 'tag' and 'folder'
