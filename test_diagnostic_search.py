from diagnostic_search import DiagnosticSearch


class FakeBackend:
    def embed(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["why did package signing fail?"]
        return [[0.2, 0.8]]

    def query(self, collection: str, embedding: list[float], top_k: int) -> dict:
        assert (collection, embedding, top_k) == ("developer-tools", [0.2, 0.8], 6)
        return {
            "matches": [
                {
                    "id": "private-note",
                    "score": 0.99,
                    "metadata": {
                        "title": "Patient-linked investigation",
                        "summary": "Restricted incident notes",
                        "kind": "diagnostic",
                        "visibility": "internal",
                        "contains_sensitive_data": True,
                    },
                },
                {
                    "id": "build-1842",
                    "score": 0.78,
                    "metadata": {
                        "title": "Build 1842 failed during package signing",
                        "summary": "The release runner could not find the ephemeral signing certificate.",
                        "kind": "build_event",
                        "visibility": "developer",
                        "contains_sensitive_data": False,
                    },
                },
            ]
        }

    def rerank(self, query: str, candidates: list[str], top_k: int) -> dict:
        assert "Patient-linked" not in " ".join(candidates)
        assert (query, top_k) == ("why did package signing fail?", 1)
        return {"results": [{"index": 0, "score": 0.94}]}


def test_sensitive_diagnostic_is_excluded_before_reranking() -> None:
    hits = DiagnosticSearch(FakeBackend()).search("why did package signing fail?", top_k=1)

    assert [hit.document_id for hit in hits] == ["build-1842"]
    assert hits[0].kind == "build_event"
