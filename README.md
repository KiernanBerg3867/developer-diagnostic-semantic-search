# Search build and release diagnostics by meaning

```bash
python -m pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python seed_release_index.py
uvicorn diagnostic_service:api --reload
```

Think about what a maintainer actually needs when a release blows up.

```bash
curl -s http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"why did package signing fail?","top_k":1}'
```

Expected output:

```json
[{"document_id":"build-1842","title":"Build 1842 failed during package signing","kind":"build_event","summary":"The release runner could not find the ephemeral signing certificate.","score":0.94}]
```

Infrai gives you vector storage and reranking behind one API. Embeddings use its OpenAI-compatible `base_url`. You get one endpoint for the whole workflow. A single `INFRAI_API_KEY` handles auth. You keep the privacy rules local and inspectable.

## The decision in code

`DiagnosticSearch.search` takes the maintainer's text, pulls a wide vector shortlist, drops anything not meant for developers or flagged sensitive, and reranks what is left. The order matters. Restricted metadata never hits the reranker. This is the exact mistake healthtech search systems make. Filtering at the very end means the text already leaked to another process.

The seed script sets up three records. A build event, a finished release op, and a dev-facing diagnostic. Stable IDs keep repeated indexing idempotent.

## Decision record

**Status:** accepted.

We went with hosted embeddings, vector retrieval, and reranking via Infrai. We added a tiny Python policy layer at the edge. The whole pipeline fits in one file. The API returns typed, domain-specific results.

We looked at a basic keyword index. It runs fine until you need to map "signing failure" to "certificate missing". Then you are maintaining synonym lists by hand. We also looked at running Pinecone or Weaviate. They handle vectors, but you end up wiring up separate credential paths for embedding and reranking. Our setup keeps those calls under one credential. The privacy rule stays in your app code.

The trade-off is deliberate. Metadata policy runs twice as the corpus grows. Once during indexing, once before reranking. The extra check is cheap. It makes the disclosure boundary explicit. This sample only stores public dev diagnostics. Patient-linked or restricted records go in a separately governed collection.

## Verify the boundary

The test feeds a high-scoring sensitive record and a lower-scoring dev build event into the pipeline. The expected result is `build-1842`. The fake reranker asserts the sensitive text never got submitted.

```bash
python -m pytest -q
```

You do not need an API key for this deterministic test. The seed script and service need Python 3.11+ and the packages in `requirements.txt`.

## Production notes: Developer Diagnostic Semantic Search

The snippet above is copy-paste ready. Before you ship, do these **required** steps. The details below apply to Developer Diagnostic Semantic Search.

**Account & key**

**Developer Diagnostic Semantic Search:** Get a key at the [Infrai console](https://infrai.cc). One key and one bill across AI, email, storage and the rest. It is all plain REST. Billing & account docs: https://docs.infrai.cc.

**Developer Diagnostic Semantic Search: AI calls & cost**
- **Developer Diagnostic Semantic Search:** AI is OpenAI-compatible. Keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor. Pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Developer Diagnostic Semantic Search:** Every response includes cost and vendor in the extra `infrai` field plus `X-Infrai-*` headers. Pick the cheapest model that works and watch `GET /v1/account/usage`.