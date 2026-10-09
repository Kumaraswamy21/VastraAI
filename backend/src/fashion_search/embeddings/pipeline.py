"""Idempotent catalog embedding pipeline for the configured provider."""

from __future__ import annotations

from dataclasses import dataclass, field

from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import configure_logging, get_logger
from fashion_search.ai.factory import get_embedding_identity, get_embedding_provider
from fashion_search.embeddings.base import EmbeddingProvider
from fashion_search.embeddings.normalize import normalize_product_text, text_hash
from fashion_search.embeddings.repository import (
    iter_product_batches,
    mark_processing,
    needs_embedding,
    product_as_mapping,
    recover_stale_processing,
    save_completed,
    save_failed,
)

logger = get_logger(__name__)


@dataclass
class PipelineStats:
    """Counters for one embedding run."""

    inspected: int = 0
    skipped: int = 0
    required: int = 0
    embedded: int = 0
    failed: int = 0
    api_requests: int = 0
    recovered_stale: int = 0
    dry_run: bool = False
    details: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "inspected": self.inspected,
            "skipped": self.skipped,
            "required": self.required,
            "embedded": self.embedded,
            "failed": self.failed,
            "api_requests": self.api_requests,
            "recovered_stale": self.recovered_stale,
            "dry_run": self.dry_run,
        }


@dataclass
class _WorkItem:
    product_id: int
    text: str
    digest: str


def run_embedding_pipeline(
    *,
    dry_run: bool = False,
    limit: int | None = None,
    batch_size: int | None = None,
    settings: Settings | None = None,
    embedder: EmbeddingProvider | None = None,
) -> PipelineStats:
    """Normalize, skip unchanged rows, embed stale products, persist vectors."""
    configure_logging()
    cfg = settings or get_settings()
    stats = PipelineStats(dry_run=dry_run)
    chunk = batch_size or cfg.embedding_batch_size

    if not dry_run:
        stats.recovered_stale = recover_stale_processing(cfg)
        if stats.recovered_stale:
            logger.info("recovered_stale_processing count=%s", stats.recovered_stale)

    worker = embedder
    configured = get_embedding_identity(cfg)
    provider_name = _string_attr(worker, "name") or configured.provider
    model_name = _string_attr(worker, "model_name") or configured.model
    dimensions = _int_attr(worker, "dimensions") or configured.dimensions
    pending: list[_WorkItem] = []

    for products in iter_product_batches(chunk, limit=limit):
        for product in products:
            stats.inspected += 1
            text = normalize_product_text(product_as_mapping(product))
            if not text.strip():
                stats.failed += 1
                stats.required += 1
                if not dry_run:
                    save_failed(product.id, "normalized embedding text is empty")
                continue
            digest = text_hash(text)
            if not needs_embedding(
                product,
                text_digest=digest,
                model=model_name,
                dimensions=dimensions,
                provider=provider_name,
            ):
                stats.skipped += 1
                continue
            stats.required += 1
            pending.append(_WorkItem(product.id, text, digest))
            if len(pending) >= chunk:
                worker = _ensure_worker(worker, dry_run=dry_run, settings=cfg)
                _flush_batch(pending, stats, worker=worker, settings=cfg, dry_run=dry_run)
                pending.clear()

    if pending:
        worker = _ensure_worker(worker, dry_run=dry_run, settings=cfg)
        _flush_batch(pending, stats, worker=worker, settings=cfg, dry_run=dry_run)

    if worker is not None:
        stats.api_requests = getattr(worker, "api_request_count", 0)

    logger.info(
        "embedding_pipeline_done inspected=%s skipped=%s required=%s embedded=%s failed=%s api_requests=%s dry_run=%s",
        stats.inspected,
        stats.skipped,
        stats.required,
        stats.embedded,
        stats.failed,
        stats.api_requests,
        dry_run,
    )
    return stats


def _ensure_worker(
    worker: EmbeddingProvider | None,
    *,
    dry_run: bool,
    settings: Settings,
) -> EmbeddingProvider | None:
    """Create the configured provider only when a live run has work to do."""
    if dry_run:
        return None
    if worker is not None:
        return worker
    return get_embedding_provider(settings)


def _flush_batch(
    items: list[_WorkItem],
    stats: PipelineStats,
    *,
    worker: EmbeddingProvider | None,
    settings: Settings,
    dry_run: bool,
) -> None:
    if dry_run or worker is None:
        return
    ids = [item.product_id for item in items]
    mark_processing(ids)
    try:
        texts = [item.text for item in items]
        vectors = worker.embed_documents(texts)
        if not isinstance(vectors, list) and hasattr(worker, "embed_texts"):
            vectors = worker.embed_texts(texts)
    except Exception as exc:
        logger.exception("embedding_batch_failed provider=%s count=%s", worker.name, len(items))
        for item in items:
            save_failed(item.product_id, str(exc))
            stats.failed += 1
        return

    for item, vector in zip(items, vectors, strict=True):
        try:
            save_completed(
                product_id=item.product_id,
                vector=vector,
                text_digest=item.digest,
                provider=_string_attr(worker, "name") or get_embedding_identity(settings).provider,
                model=_string_attr(worker, "model_name") or get_embedding_identity(settings).model,
                dimensions=_int_attr(worker, "dimensions") or get_embedding_identity(settings).dimensions,
            )
            stats.embedded += 1
        except Exception as exc:
            logger.exception("persist_failed product_id=%s", item.product_id)
            save_failed(item.product_id, str(exc))
            stats.failed += 1


def _string_attr(value: object | None, name: str) -> str | None:
    result = getattr(value, name, None)
    return result if isinstance(result, str) else None


def _int_attr(value: object | None, name: str) -> int | None:
    result = getattr(value, name, None)
    return result if isinstance(result, int) else None
