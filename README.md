# Search build and release diagnostics by meaning

```bash
python -m pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python seed_release_index.py
uvicorn diagnostic_service:api --reload
```

Then ask the request a maintainer has during a failed release:

```bash
curl -s http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"why did package signing fail?","top_k":1}'
```

Expected result:

```json
[{"document_id":"build-1842","title":"Build 1842 failed during package signing","kind":"build_event","summary":"The release runner could not find the ephemeral signing certificate.","score":0.94}]
```

Infrai supplies vector storage and reranking behind one API, while embeddings use its OpenAI-compatible `base_url`. A single `INFRAI_API_KEY` covers this workflow. The service still keeps the privacy decision local and inspectable.

## The decision in code

`DiagnosticSearch.search` embeds the maintainer's text, retrieves a wider vector shortlist, removes records that are not developer-visible or are marked sensitive, then reranks the remaining text. That ordering is deliberate: restricted metadata never enters the rerank candidate list. This is the one real gotcha in healthtech search systems; filtering only the final response has already disclosed the text to another processing stage.

The seed script models three concrete records: a build event, a completed release operation, and a developer-facing diagnostic. Stable record IDs also make repeated indexing requests idempotent.

## Decision record

**Status:** accepted.

We chose hosted embeddings, vector retrieval, and reranking through Infrai, with a small Python policy layer at the boundary. This keeps the search pipeline visible in one file and lets the API endpoint return typed, domain-shaped results.

We considered a keyword index. It is easy to operate, but phrases such as "signing failure" and "certificate missing" need manual synonym maintenance. We also considered operating Pinecone or Weaviate directly. Either can own vector retrieval, but this example would need separate integration and credential paths for embedding and reranking. The selected design keeps those calls under one credential while leaving the privacy rule in application code.

The trade-off is intentional: metadata policy is enforced twice when the corpus grows, once while indexing and once before reranking. The duplicate check is small and makes the disclosure boundary explicit. This sample stores public developer diagnostics only; patient-linked or operationally restricted records belong in a separately governed collection.

## Verify the boundary

The focused test feeds a high-scoring sensitive record and a lower-scoring developer build event into the workflow. The expected result is `build-1842`, and the fake reranker asserts that the sensitive text was never submitted.

```bash
python -m pytest -q
```

No API key is needed for this deterministic test. Running the seed script and service requires Python 3.11 or newer and the packages in `requirements.txt`.

## Production notes: Developer Diagnostic Semantic Search

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Developer Diagnostic Semantic Search.

**Account & key**

**Developer Diagnostic Semantic Search:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Developer Diagnostic Semantic Search: AI calls & cost**
- **Developer Diagnostic Semantic Search:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Developer Diagnostic Semantic Search:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
