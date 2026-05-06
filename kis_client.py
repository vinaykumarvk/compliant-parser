from __future__ import annotations

"""HTTP adapter from compliant-parser to Knowledge Intelligence Service."""

import json
import hashlib
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


class KISClientError(RuntimeError):
    pass


class KISUnavailable(KISClientError):
    pass


SECTION_DISCLAIMER = (
    "Final legal determination rests with the Investigating Officer and superior officers. "
    "These are AI-generated suggestions only."
)

KB_POLICY = "policy"
KB_CASES = "cases"


@dataclass(frozen=True)
class KISConfig:
    enabled: bool
    base_url: str
    api_key: str
    domain_id: str
    knowledge_base_id: str
    provider: str = "self_hosted"
    model: str = "llama3-legal-local"
    timeout_seconds: float = 20.0


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _is_true(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def get_kis_config() -> KISConfig:
    return KISConfig(
        enabled=_is_true("IQW_KIS_ENABLED", False),
        base_url=(_env("IQW_KIS_BASE_URL") or "").rstrip("/"),
        api_key=_env("IQW_KIS_API_KEY") or "",
        domain_id=_env("IQW_KIS_DOMAIN") or "",
        knowledge_base_id=_env("IQW_KIS_KB") or "",
        provider=_env("IQW_KIS_PROVIDER", "self_hosted") or "self_hosted",
        model=_env("IQW_KIS_MODEL", "llama3-legal-local") or "llama3-legal-local",
        timeout_seconds=float(_env("IQW_KIS_TIMEOUT_SECONDS", "20") or "20"),
    )


@dataclass(frozen=True)
class MultiKBConfig:
    policy: KISConfig
    cases: KISConfig


def get_multi_kb_config() -> MultiKBConfig:
    enabled = _is_true("IQW_KIS_ENABLED", False)
    base_url = (_env("IQW_KIS_BASE_URL") or "").rstrip("/")
    api_key = _env("IQW_KIS_API_KEY") or ""
    domain_id = _env("IQW_KIS_DOMAIN") or ""
    provider = _env("IQW_KIS_PROVIDER", "self_hosted") or "self_hosted"
    model = _env("IQW_KIS_MODEL", "llama3-legal-local") or "llama3-legal-local"
    timeout = float(_env("IQW_KIS_TIMEOUT_SECONDS", "20") or "20")
    fallback_kb = _env("IQW_KIS_KB") or ""
    policy_kb = _env("IQW_KIS_KB_POLICY") or fallback_kb
    cases_kb = _env("IQW_KIS_KB_CASES") or fallback_kb
    return MultiKBConfig(
        policy=KISConfig(
            enabled=enabled, base_url=base_url, api_key=api_key,
            domain_id=domain_id, knowledge_base_id=policy_kb,
            provider=provider, model=model, timeout_seconds=timeout,
        ),
        cases=KISConfig(
            enabled=enabled, base_url=base_url, api_key=api_key,
            domain_id=domain_id, knowledge_base_id=cases_kb,
            provider=provider, model=model, timeout_seconds=timeout,
        ),
    )


def get_kis_client(kb_name: str = KB_CASES) -> KISClient:
    multi = get_multi_kb_config()
    if kb_name == KB_POLICY:
        return KISClient(config=multi.policy)
    if kb_name == KB_CASES:
        return KISClient(config=multi.cases)
    raise ValueError(f"Unknown KB: {kb_name}")


def is_kis_configured(config: Optional[KISConfig] = None) -> bool:
    config = config or get_kis_config()
    return bool(config.enabled and config.base_url and config.api_key and config.domain_id and config.knowledge_base_id)


def kis_status(config: Optional[KISConfig] = None) -> dict[str, Any]:
    config = config or get_kis_config()
    return {
        "enabled": config.enabled,
        "configured": is_kis_configured(config),
        "base_url_configured": bool(config.base_url),
        "credential_configured": bool(config.api_key),
        "domain_id": config.domain_id or None,
        "knowledge_base_id": config.knowledge_base_id or None,
        "provider": config.provider,
        "model": config.model,
    }


class KISClient:
    def __init__(self, config: Optional[KISConfig] = None) -> None:
        self.config = config or get_kis_config()
        if not is_kis_configured(self.config):
            raise KISUnavailable("KIS adapter is not configured.")

    def _request(self, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.config.api_key,
                "X-Domain-ID": self.config.domain_id,
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise KISClientError(f"KIS HTTP {exc.code}: {body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise KISUnavailable(f"KIS is unavailable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise KISUnavailable("KIS request timed out.") from exc

    def _get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def _kb_path(self, suffix: str) -> str:
        return f"/api/v1/domains/{self.config.domain_id}/knowledge-bases/{self.config.knowledge_base_id}{suffix}"

    def _domain_path(self, suffix: str) -> str:
        return f"/api/v1/domains/{self.config.domain_id}{suffix}"

    def bns_mapping(self, complaint_text: str) -> dict[str, Any]:
        path = self._kb_path("/reasoning/bns-mapping")
        return self._post(
            path,
            {
                "complaint_text": complaint_text,
                "provider": self.config.provider,
                "model": self.config.model,
            },
        )

    def hybrid_search(self, query: str, *, top_k: int = 5) -> dict[str, Any]:
        return self._post(self._kb_path("/search/hybrid"), {"query": query, "top_k": top_k})

    def ingest_source(
        self,
        *,
        title: str,
        raw_text: str,
        source_uri: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._post(
            self._kb_path("/sources"),
            {
                "title": title,
                "raw_text": raw_text,
                "source_uri": source_uri,
                "metadata": metadata or {},
            },
        )

    def create_fact(
        self,
        *,
        subject: str,
        predicate: str,
        object_value: str,
        confidence: float = 0.86,
        source_document_id: Optional[str] = None,
        citation: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._post(
            self._kb_path("/facts"),
            {
                "subject": subject,
                "predicate": predicate,
                "object_value": object_value,
                "confidence": confidence,
                "source_document_id": source_document_id,
                "citation": citation or {},
            },
        )

    def review_fact(self, fact_id: str, *, status: str = "approved") -> dict[str, Any]:
        return self._post(self._kb_path(f"/facts/{fact_id}:review"), {"status": status})

    def promote_fact(self, fact_id: str) -> dict[str, Any]:
        return self._post(self._kb_path(f"/graph/facts/{fact_id}:promote"), {})

    def compile_wiki_article(self, *, title: str, source_document_id: Optional[str] = None) -> dict[str, Any]:
        return self._post(
            self._kb_path("/wiki/articles:compile"),
            {"title": title, "source_document_id": source_document_id},
        )

    def run_quality_gates(self) -> dict[str, Any]:
        return self._post(self._kb_path("/quality-gates:run"), {})

    def create_snapshot(self) -> dict[str, Any]:
        return self._post(self._kb_path("/snapshots"), {})

    def publish_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        return self._post(self._kb_path(f"/snapshots/{snapshot_id}:publish"), {})

    def latest_snapshot(self) -> dict[str, Any]:
        return self._get(self._kb_path("/snapshots/latest"))

    def graph_stats(self) -> dict[str, Any]:
        return self._get(self._kb_path("/graph/stats"))

    def list_wiki_articles(self) -> dict[str, Any]:
        return self._get(self._kb_path("/wiki/articles"))

    def list_facts(self) -> dict[str, Any]:
        return self._get(self._kb_path("/facts"))

    def maintenance_dashboard(self) -> dict[str, Any]:
        return self._get(self._domain_path("/maintenance/dashboard"))

    def create_provider(self, *, provider: str, allowed_models: list[str], active: bool = True, budget: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self._post(
            self._domain_path("/providers"),
            {
                "provider": provider,
                "allowed_models": allowed_models,
                "active": active,
                "budget": budget or {},
            },
        )

    def update_provider(
        self,
        provider_config_id: str,
        *,
        allowed_models: Optional[list[str]] = None,
        active: Optional[bool] = None,
        budget: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        payload = {
            key: value
            for key, value in {
                "allowed_models": allowed_models,
                "active": active,
                "budget": budget,
            }.items()
            if value is not None
        }
        return self._request("PATCH", self._domain_path(f"/providers/{provider_config_id}"), payload)

    def create_credential(self, provider_config_id: str, *, api_key: str, expires_at: Optional[str] = None) -> dict[str, Any]:
        return self._post(
            self._domain_path(f"/providers/{provider_config_id}/credentials"),
            {"api_key": api_key, "expires_at": expires_at},
        )

    def revoke_credential(self, provider_config_id: str, credential_id: str) -> dict[str, Any]:
        return self._post(self._domain_path(f"/providers/{provider_config_id}/credentials/{credential_id}:revoke"), {})

    def rebuild_knowledge_base(
        self,
        *,
        rebuild_vectors: bool = True,
        recompile_wiki: bool = True,
        promote_facts: bool = True,
        create_snapshot: bool = False,
        publish_snapshot: bool = False,
    ) -> dict[str, Any]:
        return self._post(
            self._kb_path("/maintenance:rebuild"),
            {
                "rebuild_vectors": rebuild_vectors,
                "recompile_wiki": recompile_wiki,
                "promote_facts": promote_facts,
                "create_snapshot": create_snapshot,
                "publish_snapshot": publish_snapshot,
            },
        )

    def rollback_snapshot(self, version: int) -> dict[str, Any]:
        return self._post(self._kb_path("/snapshots:rollback"), {"version": version})


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _get_nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _document_text(record_id: str, file_name: str, parsed_output: dict[str, Any], document_format: str) -> tuple[str, dict[str, Any]]:
    from privacy import protect_for_llm

    fir = parsed_output.get("fir_draft") or {}
    raw_text = "\n\n".join(
        item
        for item in [
            f"Complaint parser history record: {record_id}",
            f"File name: {file_name}",
            f"Document format: {document_format or parsed_output.get('document_type') or 'UNKNOWN'}",
            "Summary:",
            _safe_text(parsed_output.get("summary")),
            "Complaint:",
            _safe_text(parsed_output.get("complaint")),
            "FIR draft:",
            _safe_text(fir.get("formatted_text") or fir.get("narrative") or fir),
            "Gaps:",
            _safe_text(parsed_output.get("gaps")),
        ]
        if item and item != "{}"
    )
    _protected_system, protected_user, pii_context = protect_for_llm("", raw_text)
    pii_context.assert_safe_for_llm(protected_user, context="kis_source_ingest")
    return protected_user, pii_context.metadata()


def _source_title(record_id: str, file_name: str) -> str:
    safe_name = re.sub(r"\s+", " ", (file_name or "document").strip()) or "document"
    digest = hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:8]
    return f"Uploaded complaint document {digest}: {safe_name}"


def _incident_category(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ("stolen", "theft", "steal", "snatch", "dishonest taking")):
        return "theft_or_property_loss"
    if any(term in lowered for term in ("accident", "collision", "hit ", "vehicle", "injury")):
        return "road_accident_or_injury"
    if any(term in lowered for term in ("assault", "threat", "hurt")):
        return "assault_or_threat"
    if "missing" in lowered:
        return "missing_person_or_item"
    return "general_complaint"


def _section_codes(parsed_output: dict[str, Any]) -> list[str]:
    values = _get_nested(parsed_output, "fir_draft", "proposed_bns_sections") or []
    if isinstance(values, dict):
        values = [values]
    if not isinstance(values, list):
        return []
    codes: list[str] = []
    for value in values:
        if isinstance(value, str):
            code = value
        elif isinstance(value, dict):
            code = value.get("section_code") or value.get("section") or value.get("section_number") or value.get("code")
        else:
            code = None
        if code:
            code = str(code).strip().upper()
            if code.isdigit():
                code = f"BNS-{code}"
            codes.append(code)
    return sorted(set(codes))


def _deterministic_facts(
    *,
    record_id: str,
    parsed_output: dict[str, Any],
    document_format: str,
    masked_text: str,
) -> list[tuple[str, str, float]]:
    facts = [
        ("source_system", "complaint_parser_history", 0.99),
        ("document_format", document_format or parsed_output.get("document_type") or "UNKNOWN", 0.95),
        ("incident_category", _incident_category(masked_text), 0.82),
    ]
    language = _get_nested(parsed_output, "language", "detected_name") or _get_nested(parsed_output, "language", "detected")
    if language:
        facts.append(("detected_language", str(language), 0.9))
    station = _get_nested(parsed_output, "fir_draft", "jurisdiction", "police_station")
    if station:
        facts.append(("police_station", str(station), 0.8))
    confidence = parsed_output.get("completeness_score") or _get_nested(parsed_output, "confidence", "overall")
    if confidence is not None:
        facts.append(("parse_confidence", str(confidence), 0.75))
    for code in _section_codes(parsed_output):
        facts.append(("proposed_bns_section", code, 0.9))
    return [(predicate, str(object_value), confidence) for predicate, object_value, confidence in facts if str(object_value).strip()]


def index_uploaded_document_via_kis(
    *,
    record_id: str,
    file_name: str,
    parsed_output: dict[str, Any],
    document_format: str,
    publish_snapshot: bool = False,
    client: Optional[KISClient] = None,
) -> dict[str, Any]:
    if not is_kis_configured():
        return {"enabled": False, "indexed": False, "reason": "kis_not_configured"}
    if not isinstance(parsed_output, dict):
        return {"enabled": True, "indexed": False, "reason": "parsed_output_not_object"}

    client = client or get_kis_client(KB_CASES)
    masked_text, privacy_summary = _document_text(record_id, file_name, parsed_output, document_format)
    title = _source_title(record_id, file_name)
    source_uri = f"complaint-parser://history/{record_id}"
    ingested = client.ingest_source(
        title=title,
        raw_text=masked_text,
        source_uri=source_uri,
        metadata={
            "origin": "complaint_parser_history",
            "complaint_parser_record_id": record_id,
            "file_name": file_name,
            "document_format": document_format,
            "masked_before_kis_ingest": True,
            "privacy_summary": privacy_summary,
        },
    )
    source = ingested["source"]
    citation = {"source_document_id": source["id"], "title": title, "source_uri": source_uri}
    subject = f"complaint_parser_record:{record_id}"
    facts = []
    promoted = []
    for predicate, object_value, confidence in _deterministic_facts(
        record_id=record_id,
        parsed_output=parsed_output,
        document_format=document_format,
        masked_text=masked_text,
    ):
        fact = client.create_fact(
            subject=subject,
            predicate=predicate,
            object_value=object_value,
            confidence=confidence,
            source_document_id=source["id"],
            citation=citation,
        )
        reviewed = client.review_fact(fact["id"], status="approved")
        promoted.append(client.promote_fact(reviewed["id"]))
        facts.append(reviewed)

    article = client.compile_wiki_article(title=title, source_document_id=source["id"])
    quality_report = client.run_quality_gates()
    published_snapshot = None
    if publish_snapshot and quality_report.get("passed"):
        snapshot = client.create_snapshot()
        published_snapshot = client.publish_snapshot(snapshot["id"])
    return {
        "enabled": True,
        "indexed": True,
        "idempotent_replay": bool(ingested.get("idempotent_replay")),
        "source_id": source["id"],
        "chunk_count": len(ingested.get("chunks") or []),
        "fact_count": len(facts),
        "graph_edge_count": len(promoted),
        "wiki_article_id": article["id"],
        "quality_passed": quality_report.get("passed"),
        "published_snapshot_id": published_snapshot.get("id") if published_snapshot else None,
        "privacy_summary": privacy_summary,
    }


def recommend_sections_via_kis(text: str, *, show_all: bool = False) -> Optional[dict[str, Any]]:
    if not is_kis_configured():
        return None
    run = get_kis_client(KB_POLICY).bns_mapping(text)
    data = dict(run.get("result") or {})
    data.setdefault("primary_sections", [])
    data.setdefault("alternative_sections", [])
    if not show_all:
        data["primary_sections"] = [
            item for item in data.get("primary_sections", []) if float(item.get("confidence_score") or 0) >= 0.30
        ]
        data["alternative_sections"] = [
            item for item in data.get("alternative_sections", []) if float(item.get("confidence_score") or 0) >= 0.30
        ]
    provider = run.get("llm_usage", {}).get("provider") or get_kis_config().provider
    model = run.get("llm_usage", {}).get("model") or get_kis_config().model
    data.update(
        {
            "disclaimer": SECTION_DISCLAIMER,
            "model_name": f"kis:{provider}:{model}",
            "llm_provider": "kis",
            "llm_mode": run.get("status", "unknown"),
            "privacy_controls": run.get("privacy_summary", {}),
            "supported_model_family": "KIS governed hybrid retrieval + structured JSON reasoning",
            "kis_reasoning_run_id": run.get("id"),
            "kis_context_summary": run.get("context_summary", {}),
        }
    )
    return data
