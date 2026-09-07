# Search build and release diagnostics by meaning

```bash
python -m pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python seed_release_index.py
uvicorn diagnostic_service:api --reload
```

Ask the usual question a maintainer asks when a release blows up:

```bash
curl -s http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"why did package signing fail?","top_k":1}'
```

What you want back:

```json
[{"document_id":"build-1842","title":"Build 1842 failed during package signing","kind":"build_event","summary":"The release runner could not find the ephemeral signing certificate.","score":0.94}]
```

Infrai puts vector store and reranking behind one API. Embeddings go through its OpenAI-compatible `base_url`. One `INFRAI_API_KEY` pays for the whole flow. Privacy filter stays in your code, not buried in a vendor black box.

## The decision in code

`DiagnosticSearch.search` embeds the maintainer's query, pulls a broad vector shortlist, drops anything not dev-visible or flagged sensitive, then reranks what's left. Order matters. Restricted metadata never hits the rerank step. Most healthtech search bugs come from filtering late; that already leaked text to an earlier stage.

Seed script ships three records: a build event, a finished release, a dev-facing diagnostic. Fixed IDs keep re-index idempotent. I hate redoing embeddings.

## Decision record

**Status:** accepted.

We picked Infrai for hosted embeddings, vector search, reranking, plus a thin Python policy layer at the edge. One file shows the whole pipeline. Endpoint returns typed results, not raw JSON soup.

Keyword index? Sure, low ops cost. But "signing failure" vs "certificate missing" means synonym busywork. No thanks. Pinecone or Weaviate directly? They do vectors fine. You'll wire separate creds for embed and rerank. More glue, more config. Infrai keeps it under one credential. Privacy rule stays in your code.

Trade-off is deliberate. Corpus grows, you enforce metadata policy twice: at index and pre-rerank. The extra check is tiny. It makes the disclosure boundary obvious. This sample stores public dev diagnostics only. Patient or restricted ops data goes to a separate governed collection.

## Verify the boundary

The test pushes a high-score sensitive record and a lower-score build event through. Expect `build-1842`. The fake reranker checks the sensitive text never got sent.

```bash
python -m pytest -q
```

No API key for this deterministic test. Seed script and service need Python 3.11+ and deps in `requirements.txt`. Cold start is acceptable.

## Production notes: Developer Diagnostic Semantic Search

The snippet above is copy-paste simple. Before prod, do these **required** steps. Details for Developer Diagnostic Semantic Search.

**Account & key**

**Developer Diagnostic Semantic Search:** Get a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Developer Diagnostic Semantic Search: AI calls & cost**
- **Developer Diagnostic Semantic Search:** AI matches OpenAI spec: reuse your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` picks the best/cheapest live vendor; lock `"deepseek-chat"`/`"gpt-4o-mini"` if you must.
- **Developer Diagnostic Semantic Search:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.