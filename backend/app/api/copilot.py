from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agents import copilot
from app.core import audit
from app.core.ratelimit import LLM_LIMIT, limiter
from app.core.security import require_role
from app.db.models import User
from app.db.session import get_session, session_scope
from app.services.claims import get_claim_or_404

router = APIRouter(prefix="/claims", tags=["copilot"])


class CopilotIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


SUGGESTED = [
    "Why was this claim flagged?",
    "Which clauses were applied, and why?",
    "Show similar past claims",
    "How does this provider compare with its peers?",
]


@router.get("/{claim_id}/copilot")
async def history(claim_id: str, user: Annotated[User, Depends(require_role("adjuster", "auditor"))]) -> dict:
    return {"messages": await copilot.load_history(copilot.thread_id(claim_id, user.id)), "suggested": SUGGESTED}


@router.post("/{claim_id}/copilot")
@limiter.limit(LLM_LIMIT)
async def chat(
    request: Request,
    claim_id: str,
    body: CopilotIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_role("adjuster", "auditor"))],
) -> EventSourceResponse:
    await get_claim_or_404(session, claim_id)
    user_id = user.id

    async def events():
        tool_calls = 0
        async for event in copilot.chat(claim_id, user_id, body.message):
            if event["type"] == "done":
                tool_calls = event.get("tool_calls", 0)
            yield {"event": event["type"], "data": copilot.sse(event)}
        async with session_scope() as s:
            await audit.log(
                s,
                ("user", str(user_id)),
                "copilot_message",
                "claim",
                claim_id,
                {"chars": len(body.message), "tool_calls": tool_calls},
            )
            await s.commit()

    return EventSourceResponse(events())
