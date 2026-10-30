"""Hybrid policy search: pgvector cosine top 20 + Postgres full-text top 20, merged with Reciprocal Rank Fusion
(k = 60), top 6 returned. Defined terms used in a returned chunk get their definition chunk attached."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.policy.chunker import defined_terms
from app.services.policy.embed import active_model, embed_query

RRF_K = 60
CANDIDATES = 20
TOP = 6

_VECTOR_SQL = """
SELECT id FROM policy_chunks
WHERE product_id = :product_id AND embed_model = :model
  AND (CAST(:clause_type AS text) IS NULL OR clause_type = :clause_type)
ORDER BY embedding <=> CAST(:q AS vector)
LIMIT :n
"""

_KEYWORD_SQL = """
SELECT id FROM policy_chunks, websearch_to_tsquery('english', :query) q
WHERE product_id = :product_id AND tsv @@ q AND (CAST(:clause_type AS text) IS NULL OR clause_type = :clause_type)
ORDER BY ts_rank_cd(tsv, q) DESC, id
LIMIT :n
"""


def rrf(rankings: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def _row(r) -> dict:
    return {
        "id": r.id,
        "clause_no": r.clause_no,
        "section_path": r.section_path,
        "clause_type": r.clause_type,
        "page": r.page,
        "text": r.text,
    }


async def search(
    session: AsyncSession,
    product_id: str,
    query: str,
    clause_type: str | None = None,
    top: int = TOP,
    expand_definitions: bool = True,
    query_vector: list[float] | None = None,
) -> list[dict]:
    """Pass query_vector when the caller holds a database connection: embedding can wait on API rate limits."""
    q_vec = query_vector if query_vector is not None else await embed_query(query)
    params = {"product_id": product_id, "clause_type": clause_type, "n": CANDIDATES}
    vector_ids = [
        r.id
        for r in await session.execute(
            text(_VECTOR_SQL), {**params, "model": active_model(), "q": "[" + ",".join(f"{x:.6f}" for x in q_vec) + "]"}
        )
    ]
    keyword_ids = [r.id for r in await session.execute(text(_KEYWORD_SQL), {**params, "query": query})]
    fused = rrf([vector_ids, keyword_ids])[:top]
    if not fused:
        return []
    ids = [doc_id for doc_id, _ in fused]
    rows = {
        r.id: r
        for r in await session.execute(
            text("SELECT id, clause_no, section_path, clause_type, page, text FROM policy_chunks WHERE id = ANY(:ids)"),
            {"ids": ids},
        )
    }
    results = []
    for doc_id, score in fused:
        item = _row(rows[doc_id])
        item["score"] = round(score, 6)
        item["vector_rank"] = vector_ids.index(doc_id) + 1 if doc_id in vector_ids else None
        item["keyword_rank"] = keyword_ids.index(doc_id) + 1 if doc_id in keyword_ids else None
        results.append(item)
    if expand_definitions:
        await attach_definitions(session, product_id, results)
    return results


async def definitions(session: AsyncSession, product_id: str) -> dict[str, dict]:
    rows = await session.execute(
        text(
            "SELECT id, clause_no, section_path, clause_type, page, text FROM policy_chunks "
            "WHERE product_id = :p AND clause_type = 'definition' ORDER BY id"
        ),
        {"p": product_id},
    )
    out: dict[str, dict] = {}
    for r in rows:
        for term in defined_terms(r.text):
            out.setdefault(term.lower(), _row(r))
    return out


async def attach_definitions(session: AsyncSession, product_id: str, results: list[dict]) -> None:
    defs = await definitions(session, product_id)
    if not defs:
        return
    for item in results:
        lower = item["text"].lower()
        attached = [
            {"term": term, "clause_no": d["clause_no"], "text": d["text"]}
            for term, d in defs.items()
            if term in lower and d["id"] != item["id"]
        ]
        if attached:
            item["definitions"] = attached[:3]


async def get_definition(session: AsyncSession, product_id: str, term: str) -> dict | None:
    defs = await definitions(session, product_id)
    return defs.get(term.lower().strip())
