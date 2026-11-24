"""조립 지점(composition root). 어댑터를 골라 유스케이스에 꽂는 유일한 곳."""
from __future__ import annotations

from .adapters.outbound.anthropic_classifier import AnthropicClassifier
from .adapters.outbound.fastembed_embedder import FastEmbedEmbedder
from .adapters.outbound.github_history import GitHubContributionHistory
from .adapters.outbound.github_tracker import GitHubIssueTracker
from .adapters.outbound.jsonl_log import JsonlResultLog
from .application.assignment import HistoryAssigneeRecommender
from .application.ports import IssueCatalog
from .application.similarity import EmbeddingSimilarityFinder
from .application.triage import TriageIssue
from .config import Settings, load_settings


def build_classifier(settings: Settings | None = None) -> AnthropicClassifier:
    settings = settings or load_settings()
    if not settings.has_api_key:
        raise SystemExit("ANTHROPIC_API_KEY가 없습니다. IssuePilot/.env 파일에 키를 넣어 주세요.")
    return AnthropicClassifier(settings)


def build_finder(catalog: IssueCatalog, settings: Settings | None = None) -> EmbeddingSimilarityFinder:
    settings = settings or load_settings()
    return EmbeddingSimilarityFinder(
        catalog, FastEmbedEmbedder(settings.embed_model, settings.embed_cache_dir),
        top_k=settings.similar_top_k, min_similarity=settings.similar_min_similarity,
        pool_size=settings.similar_pool_size)


def build_recommender(tracker: GitHubIssueTracker) -> HistoryAssigneeRecommender:
    return HistoryAssigneeRecommender(GitHubContributionHistory(tracker.repo))


def build_triage(repo_name: str, settings: Settings | None = None) -> TriageIssue:
    settings = settings or load_settings()
    tracker = GitHubIssueTracker.connect(repo_name)
    return TriageIssue(
        tracker=tracker,
        classifier=build_classifier(settings),
        finder=build_finder(tracker, settings),
        recommender=build_recommender(tracker),
        result_log=JsonlResultLog(settings.log_path),
    )
