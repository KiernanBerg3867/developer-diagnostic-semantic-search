from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from diagnostic_search import DiagnosticSearch, InfraiClient, InfraiError


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)
    kind: str | None = Field(default=None, pattern="^(build_event|release_operation|diagnostic)$")


class SearchHit(BaseModel):
    document_id: str
    title: str
    kind: str
    summary: str
    score: float


@asynccontextmanager
async def lifespan(application: FastAPI):
    client = InfraiClient()
    application.state.client = client
    application.state.search = DiagnosticSearch(client)
    yield
    client.close()


api = FastAPI(title="Developer tools semantic search", lifespan=lifespan)


@api.post("/search", response_model=list[SearchHit])
def search(request: SearchRequest) -> list[SearchHit]:
    try:
        hits = api.state.search.search(request.query, request.top_k, request.kind)
        return [SearchHit(**hit.__dict__) for hit in hits]
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
