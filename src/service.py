import json
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .db import AsyncSessionLocal
from .models import Agent, AgentStatus, Lead, LeadStatus
from .redis_client import redis_client, EVENT_CHANNEL
from .logger import get_logger

logger = get_logger()


# -- On lead creation --

async def persist_lead(db: AsyncSession, lead: Lead):
    """
    Saves lead as PENDING.
    """
    async with db.begin():
        lead.status = LeadStatus.PENDING
        db.add(lead)

async def try_assign_lead(db: AsyncSession, lead: Lead) -> Optional[str]:
    """
    Tries to assign lead to LRU eligible agent.
    """
    agent = await _search_for_agent(db, lead)
    if agent:
        await _assign(db, agent, lead)
    else:
        logger.info(f"No eligible agents found; leaving lead_id={lead.lead_id} as PENDING.")
        


# -- On sales agent release --

async def release_agent(db: AsyncSession, agent_id: str) -> Optional[Agent]:
    """
    Marks agent as AVAILABLE.
    """
    async with db.begin():
        agent_statement = select(Agent).where(Agent.agent_id == agent_id).with_for_update()
        agent_res = await db.execute(agent_statement)
        agent = agent_res.scalars().first()

        if agent:
            agent.status = AgentStatus.AVAILABLE
            db.add(agent)

        return agent

async def try_assign_agent(db: AsyncSession, agent: Agent):
    """
    Tries to assign agent to oldest lead if eligible, otherwise marks agent as AVAILABLE.
    """
    lead = await _search_for_lead(db, agent)
    if lead:
        await _assign(db, agent, lead)
    else:
        logger.info(f"No eligible leads found; leaving agent_id={agent.agent_id} as AVAILABLE.")


# -- Background task wrappers

async def try_assign_lead_bg(lead_id: str) -> None:
    async with AsyncSessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if lead:
            await try_assign_lead(session, lead)
            await session.commit()


async def try_assign_agent_bg(agent_id: str) -> None:
    async with AsyncSessionLocal() as session:
        agent = await session.get(Agent, agent_id)
        if agent:
            await try_assign_agent(session, agent)
            await session.commit()


# -- Helpers --

async def _search_for_agent(db: AsyncSession, lead: Lead) -> Optional[Agent]:
    # Find the LRU agent, and lock it
    statement = (
        select(Agent)
        .where(
            Agent.status == AgentStatus.AVAILABLE,
            Agent.type == lead.type,
            Agent.tier >= lead.min_tier,
            Agent.region == lead.region,
            Agent.language == lead.language,
        )
        .order_by(Agent.last_used.asc().nulls_first())
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    result = await db.execute(statement)
    return result.scalars().first()


async def _search_for_lead(db: AsyncSession, agent: Agent) -> Optional[Lead]:
    # Find the oldest FIFO pending lead that matches, and lock it
    statement = (
        select(Lead)
        .where(
            Lead.status == LeadStatus.PENDING,
            Lead.type == agent.type,
            Lead.min_tier <= agent.tier,
            Lead.region == agent.region,
            Lead.language == agent.language,
        )
        .order_by(Lead.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(statement)
    lead = result.scalars().first()
    return lead


async def _assign(db: AsyncSession, agent: Agent, lead: Lead) -> None:
    """
    Atomically updates states for an assigned agent and lead, stages the changes
    in the active session, logs the match, and publishes the event to Redis.
    """
    agent.status = AgentStatus.BUSY
    agent.last_used = datetime.now(timezone.utc).replace(tzinfo=None)
    lead.status = LeadStatus.ASSIGNED

    db.add_all([agent, lead])
    logger.info(f"Matched lead_id={lead.lead_id} with agent_id={agent.agent_id}.")

    await _publish_event(lead.lead_id, agent.agent_id)


async def _publish_event(lead_id: str, agent_id: str) -> None:
    """Publishes a NEW_LEAD event to the central Redis event channel."""
    event_payload = json.dumps({
        "event": "NEW_LEAD",
        "lead_id": lead_id,
        "agent_id": agent_id
    })
    await redis_client.publish(EVENT_CHANNEL, event_payload)