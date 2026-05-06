from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import (
    audit,
    domains,
    evaluations,
    facts,
    feedback,
    graph,
    health,
    knowledge_bases,
    maintenance,
    ontology,
    prompts,
    providers,
    retention,
    reasoning,
    search,
    snapshots,
    sources,
    templates,
    wiki,
)
from src.config import Settings, get_settings
from src.db.migrations import run_migrations
from src.core.errors import KISError, kis_error_handler
from src.db.session import database_status, dispose_engine, get_engine, is_database_configured
from src.db.state_persistence import hydrate_store
from src.middleware.auth import APIKeyAuthMiddleware
from src.middleware.persistence import StorePersistenceMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = _app.state.settings
    _app.state.persistence_enabled = False
    if settings.require_database and not is_database_configured(settings):
        raise RuntimeError("KIS database is required but no KIS database configuration was provided.")
    if is_database_configured(settings):
        engine = get_engine(settings)
        if engine is not None and settings.auto_migrate:
            await run_migrations(engine)
        db = await database_status(settings)
        if settings.require_database and db.get("status") != "ok":
            raise RuntimeError(f"KIS database is required but is not ready: {db.get('error_type') or db.get('status')}")
        if db.get("status") == "ok":
            await hydrate_store(settings)
            _app.state.persistence_enabled = True
    yield
    await dispose_engine()


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.service_name, version=settings.service_version, lifespan=lifespan)
    app.state.settings = settings
    app.add_exception_handler(KISError, kis_error_handler)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(StorePersistenceMiddleware)
    app.add_middleware(APIKeyAuthMiddleware, settings=settings)
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(domains.router, prefix=settings.api_prefix)
    app.include_router(knowledge_bases.router, prefix=settings.api_prefix)
    app.include_router(maintenance.router, prefix=settings.api_prefix)
    app.include_router(templates.router, prefix=settings.api_prefix)
    app.include_router(providers.router, prefix=settings.api_prefix)
    app.include_router(audit.router, prefix=settings.api_prefix)
    app.include_router(retention.router, prefix=settings.api_prefix)
    app.include_router(sources.router, prefix=settings.api_prefix)
    app.include_router(search.router, prefix=settings.api_prefix)
    app.include_router(ontology.router, prefix=settings.api_prefix)
    app.include_router(facts.router, prefix=settings.api_prefix)
    app.include_router(graph.router, prefix=settings.api_prefix)
    app.include_router(wiki.router, prefix=settings.api_prefix)
    app.include_router(snapshots.router, prefix=settings.api_prefix)
    app.include_router(evaluations.router, prefix=settings.api_prefix)
    app.include_router(feedback.router, prefix=settings.api_prefix)
    app.include_router(prompts.router, prefix=settings.api_prefix)
    app.include_router(reasoning.router, prefix=settings.api_prefix)
    return app


app = create_app()
