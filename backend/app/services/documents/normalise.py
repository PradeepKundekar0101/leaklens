"""Map extracted descriptions to items.item_code (rapidfuzz score >= 85), else classify the category;
map the hospital name to a provider_id."""

from dataclasses import dataclass

from rapidfuzz import fuzz, process

from app.core.config import get_settings
from app.services.llm import client as llm
from app.services.llm import prompts
from app.services.llm.schemas import CategoryGuess

MATCH_THRESHOLD = 85
SERVICE_CODES = {"room": "ROOM", "icu": "ICU", "nursing": "NURSING", "ot": "OT", "surgeon": "SURGEON"}


@dataclass
class ItemRef:
    item_code: str
    name: str
    category: str


def match_item(description: str, items: list[ItemRef]) -> tuple[ItemRef | None, float]:
    if not items:
        return None, 0.0
    names = [i.name for i in items]
    best = process.extractOne(description, names, scorer=fuzz.token_set_ratio)
    if best is None or best[1] < MATCH_THRESHOLD:
        return None, float(best[1]) if best else 0.0
    return items[best[2]], float(best[1])


async def classify_category(description: str, fallback: str) -> str:
    settings = get_settings()
    if fallback != "other" or not settings.llm_enabled:
        return fallback
    result, _ = await llm.structured(
        model=settings.model_fast,
        system="Classify a hospital bill line into a billing category. " + prompts.UNTRUSTED_NOTE,
        user=prompts.wrap_untrusted(description),
        schema=CategoryGuess,
        max_tokens=100,
    )
    return result.category if result else fallback


def match_provider(hospital_name: str | None, providers: list[tuple[str, str]]) -> str | None:
    if not hospital_name or not providers:
        return None
    best = process.extractOne(hospital_name, [name for _, name in providers], scorer=fuzz.token_set_ratio)
    return providers[best[2]][0] if best and best[1] >= MATCH_THRESHOLD else None
