import asyncio
import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from .db import get_db
from .models import Lead, LeadCreate
from .redis_client import redis_client, EVENT_CHANNEL
from .service import persist_lead, release_agent, try_assign_lead_bg, try_assign_agent_bg

router = APIRouter()

@router.post("/lead", status_code=202)
async def create_lead(
    payload: LeadCreate, 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db)
):
    # Assume whichever platform the lead originated from appends data like
    # location, language, etc. which we will use for sales agent matching.
    new_lead = Lead.model_validate(payload)
    
    # Persist lead synchronously
    await persist_lead(db, new_lead)

    # Process lead asynchronously, since it's unknown when matching will happen.
    background_tasks.add_task(try_assign_lead_bg, new_lead.lead_id)

    return {
        "lead_id": new_lead.lead_id
    }


@router.post("/agent/{agent_id}/release")
async def release_agent_endpoint(
    agent_id: str, 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db)
):
    agent = await release_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Process potential matching after releasing agent async
    background_tasks.add_task(try_assign_agent_bg, agent.agent_id)

    return {
        "agent_id": agent_id
    }


@router.get("/event/stream")
async def event_stream():
    # Subscribe to redis pubsub.
    # This will consume the stream of any leads as soon as they get matched to an agent.
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(EVENT_CHANNEL)

    async def event_generator():
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, 
                    timeout=1.0
                )
                if message:
                    data = message["data"]
                    yield f"data: {data}\n\n"
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(EVENT_CHANNEL)
            await pubsub.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")