from __future__ import annotations

import re
from typing import Any

from src.core.errors import KISError
from src.state import STORE, new_id, utcnow


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "article"


def _broken_links(body: str, domain_id: str, knowledge_base_id: str) -> list[str]:
    existing = {
        article["title"].lower()
        for article in STORE.wiki_articles.values()
        if article["domain_id"] == domain_id and article["knowledge_base_id"] == knowledge_base_id
    }
    links = re.findall(r"\[\[([^\]]+)\]\]", body)
    links = [link for link in links if not link.startswith("PII_")]
    return sorted({link for link in links if link.lower() not in existing})


def compile_article(
    domain_id: str,
    knowledge_base_id: str,
    title: str,
    *,
    source_document_id: str | None = None,
) -> dict[str, Any]:
    chunks = [
        chunk
        for chunk in STORE.chunks.values()
        if chunk["domain_id"] == domain_id
        and chunk["knowledge_base_id"] == knowledge_base_id
        and (
            (source_document_id and chunk["source_document_id"] == source_document_id)
            or (not source_document_id and title.lower().split()[0] in chunk["text"].lower())
        )
    ]
    if not chunks:
        raise KISError("WIKI_SOURCE_NOT_FOUND", "No source chunks available for article.", status_code=404)
    citations = [chunk["citation"] for chunk in chunks[:5]]
    body = f"# {title}\n\n" + "\n\n".join(chunk["text"] for chunk in chunks[:3])
    article = {
        "id": new_id("wiki"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "slug": _slug(title),
        "title": title,
        "body": body,
        "status": "draft",
        "citations": citations,
        "broken_links": _broken_links(body, domain_id, knowledge_base_id),
        "created_at": utcnow(),
    }
    STORE.wiki_articles[article["id"]] = article
    return article


def list_articles(domain_id: str, knowledge_base_id: str) -> list[dict[str, Any]]:
    return [
        article
        for article in STORE.wiki_articles.values()
        if article["domain_id"] == domain_id and article["knowledge_base_id"] == knowledge_base_id
    ]
