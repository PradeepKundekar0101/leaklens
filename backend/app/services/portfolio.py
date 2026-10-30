"""Portfolio and provider intelligence.

observed/expected index = sum of claimed amounts / sum of expected amounts, where a claim's expected amount is
the peer-median claimed amount (training split) for the same procedure, hospital tier and city tier.
Leakage and flag rate use processed claims (those with a recommendation).
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

REFRESH_SQL = """
WITH peer AS (
    SELECT c.procedure_code, p.hospital_tier, p.city_tier,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY c.claimed_amount) AS median_amount,
           avg(c.pharmacy_amount / NULLIF(c.claimed_amount, 0)) AS peer_pharmacy
    FROM claims c JOIN providers p ON p.id = c.provider_id
    WHERE c.split = 'train'
    GROUP BY 1, 2, 3
),
base AS (
    SELECT c.provider_id,
           date_trunc('month', c.admission_at)::date AS period,
           c.claimed_amount,
           COALESCE(peer.median_amount, c.claimed_amount) AS expected,
           c.pharmacy_amount / NULLIF(c.claimed_amount, 0) AS pharmacy_share,
           peer.peer_pharmacy,
           r.leakage_amount,
           r.action
    FROM claims c
    JOIN providers p ON p.id = c.provider_id
    LEFT JOIN peer ON peer.procedure_code = c.procedure_code AND peer.hospital_tier = p.hospital_tier
                  AND peer.city_tier = p.city_tier
    LEFT JOIN recommendations r ON r.claim_id = c.id
)
INSERT INTO provider_stats (provider_id, period, claims, claimed_total, leakage_total, flag_rate, oe_index,
                            avg_pharmacy_share, peer_pharmacy_share, updated_at)
SELECT provider_id, period, count(*), sum(claimed_amount), COALESCE(sum(leakage_amount), 0),
       COALESCE(avg(CASE WHEN action IS NULL THEN NULL WHEN action <> 'approve' THEN 1.0 ELSE 0.0 END), 0),
       sum(claimed_amount) / NULLIF(sum(expected), 0),
       COALESCE(avg(pharmacy_share), 0), COALESCE(avg(peer_pharmacy), 0), now()
FROM base
GROUP BY provider_id, period
"""


async def refresh_provider_stats(session: AsyncSession) -> int:
    await session.execute(text("DELETE FROM provider_stats"))
    result = await session.execute(text(REFRESH_SQL))
    return result.rowcount or 0


RANKING_SQL = """
SELECT p.id, p.name, p.city, p.city_tier, p.hospital_tier, p.nabh, p.network,
       sum(s.claims) AS claims, sum(s.claimed_total) AS claimed_total, sum(s.leakage_total) AS leakage_total,
       sum(s.flag_rate * s.claims) / NULLIF(sum(s.claims), 0) AS flag_rate,
       sum(s.oe_index * s.claimed_total) / NULLIF(sum(s.claimed_total), 0) AS oe_index_weighted,
       sum(s.claimed_total) / NULLIF(sum(s.claimed_total / NULLIF(s.oe_index, 0)), 0) AS oe_index,
       sum(s.avg_pharmacy_share * s.claims) / NULLIF(sum(s.claims), 0) AS avg_pharmacy_share,
       sum(s.peer_pharmacy_share * s.claims) / NULLIF(sum(s.claims), 0) AS peer_pharmacy_share
FROM providers p JOIN provider_stats s ON s.provider_id = p.id
GROUP BY p.id
"""
