from __future__ import annotations

from diagnostic_search import InfraiClient


DOCUMENTS = [
    {
        "id": "build-1842",
        "title": "Build 1842 failed during package signing",
        "kind": "build_event",
        "summary": "The release runner could not find the ephemeral signing certificate.",
    },
    {
        "id": "release-2026-09-03",
        "title": "Mobile SDK 4.8 release completed",
        "kind": "release_operation",
        "summary": "Artifacts were signed, checksummed, and published to the developer channel.",
    },
    {
        "id": "diag-token-scope",
        "title": "Deployment token rejected by package registry",
        "kind": "diagnostic",
        "summary": "Issue a replacement token with package write scope, then rerun the release job.",
    },
]


def main() -> None:
    client = InfraiClient()
    try:
        texts = [f"{item['title']}\n{item['summary']}" for item in DOCUMENTS]
        embeddings = client.embed(texts)
        dimension = len(embeddings[0])
        client.create_collection("developer-tools", dimension)
        vectors = [
            {
                "id": item["id"],
                "values": embedding,
                "metadata": {
                    **item,
                    "visibility": "developer",
                    "contains_sensitive_data": False,
                },
            }
            for item, embedding in zip(DOCUMENTS, embeddings, strict=True)
        ]
        client.upsert("developer-tools", vectors)
        print(f"Indexed {len(vectors)} developer-tool records.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
