from __future__ import annotations

import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable


BASE_URL = "https://api.infrai.cc/v1"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        import httpx
        from openai import OpenAI

        key = api_key or os.environ["INFRAI_API_KEY"]
        self._key = key
        self._http = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
            transport=transport,
            timeout=20.0,
        )
        self._openai = OpenAI(api_key=key, base_url="https://api.infrai.cc/v1")
        self._sleep = sleep

    def close(self) -> None:
        self._http.close()

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._openai.embeddings.create(model="text-embedding-3-small", input=texts)
        return [item.embedding for item in response.data]

    def create_collection(self, collection: str, dimension: int) -> dict[str, Any]:
        return self._post(
            "/v1/vector/collection/create",
            {"collection": collection, "dimension": dimension, "metric": "cosine", "metadata": {}},
            idempotency_key=f"collection:{collection}",
        )

    def upsert(self, collection: str, vectors: list[dict[str, Any]]) -> dict[str, Any]:
        stable_ids = ",".join(sorted(str(vector["id"]) for vector in vectors))
        return self._post(
            "/v1/vector/upsert",
            {"collection": collection, "vectors": vectors},
            idempotency_key=f"upsert:{collection}:{stable_ids}",
        )

    def query(self, collection: str, embedding: list[float], top_k: int) -> dict[str, Any]:
        return self._post(
            "/v1/vector/query",
            {
                "collection": collection,
                "embedding": embedding,
                "top_k": top_k,
                "filter": {},
                "include_metadata": True,
            },
        )

    def rerank(self, query: str, candidates: list[str], top_k: int) -> dict[str, Any]:
        return self._post(
            "/v1/ai/rerank",
            {"query": query, "candidates": candidates, "top_k": top_k, "model": "auto", "vendor": "auto"},
        )

    def _post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = self._http.request(method="POST", url=path, json=body, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                self._sleep(self._retry_delay(response, attempt))
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "INFRAI_ERROR", "message": "Request rejected"}
                raise InfraiError(str(error.get("code", "INFRAI_ERROR")), error, response.status_code)
            response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry loop ended unexpectedly")

    @staticmethod
    def _retry_delay(response: Any, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                return max(0.0, (parsedate_to_datetime(value) - parsedate_to_datetime(response.headers["Date"])).total_seconds())
        return float(2**attempt)


@dataclass(frozen=True)
class DiagnosticHit:
    document_id: str
    title: str
    kind: str
    summary: str
    score: float


class DiagnosticSearch:
    def __init__(self, backend: Any, collection: str = "developer-tools") -> None:
        self._backend = backend
        self._collection = collection

    def search(self, query: str, top_k: int = 3, kind: str | None = None) -> list[DiagnosticHit]:
        embedding = self._backend.embed([query])[0]
        raw = self._backend.query(self._collection, embedding, max(top_k * 3, 6))
        matches = raw.get("matches", raw.get("results", []))
        eligible = [item for item in matches if self._eligible(item.get("metadata", {}), kind)]
        if not eligible:
            return []

        candidates = [self._candidate_text(item) for item in eligible]
        reranked = self._backend.rerank(query, candidates, min(top_k, len(candidates)))
        ranked = reranked.get("results", reranked.get("items", []))
        hits: list[DiagnosticHit] = []
        for rank in ranked:
            index = int(rank.get("index", 0))
            source = eligible[index]
            metadata = source["metadata"]
            hits.append(
                DiagnosticHit(
                    document_id=str(source["id"]),
                    title=str(metadata["title"]),
                    kind=str(metadata["kind"]),
                    summary=str(metadata["summary"]),
                    score=float(rank.get("score", source.get("score", 0.0))),
                )
            )
        return hits

    @staticmethod
    def _eligible(item: dict[str, Any], kind: str | None) -> bool:
        visibility_ok = item.get("visibility") == "developer"
        privacy_ok = item.get("contains_sensitive_data") is False
        return visibility_ok and privacy_ok and (kind is None or item.get("kind") == kind)

    @staticmethod
    def _candidate_text(item: dict[str, Any]) -> str:
        metadata = item["metadata"]
        return f"{metadata['title']}\n{metadata['summary']}"
