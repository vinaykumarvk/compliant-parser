from __future__ import annotations

from typing import Any

from src.state import STORE


def wiki_search(domain_id: str, knowledge_base_id: str, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    terms = {term.lower() for term in query.split() if len(term) > 2}
    matches = []
    for article in STORE.wiki_articles.values():
        if article["domain_id"] != domain_id or article["knowledge_base_id"] != knowledge_base_id:
            continue
        haystack = f"{article['title']} {article['body']}".lower()
        score = sum(1 for term in terms if term in haystack)
        if score:
            matches.append(
                {
                    "id": article["id"],
                    "source": "wiki",
                    "score": round(score / max(len(terms), 1), 6),
                    "text": article["body"],
                    "citation": {"wiki_article_id": article["id"], "title": article["title"], "slug": article["slug"]},
                    "privacy_summary": {"raw_pii_sent_to_llm": False},
                }
            )
    return sorted(matches, key=lambda row: row["score"], reverse=True)[:limit]
