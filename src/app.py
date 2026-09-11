from contextlib import asynccontextmanager
from fastapi import FastAPI

from .db import init_db, AsyncSessionLocal
from .models import Agent, AgentCreate, AgentStatus
from .router import router
from .logger import get_logger

logger = get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize schema
    await init_db()

    # Insert dummy sales agents to DB
    async with AsyncSessionLocal() as session:
        initial_agents = [
            AgentCreate(agent_id="agent_1", type="special", tier=1, region="US-East"),
            AgentCreate(agent_id="agent_2", type="pro", tier=2, region="US-West"),
            AgentCreate(agent_id="agent_3", type="general", tier=1, region="US-West"),
            AgentCreate(agent_id="agent_4", type="general", tier=1, region="US-East"),
            AgentCreate(agent_id="agent_5", type="general", tier=3, region="US-East"),
            AgentCreate(agent_id="agent_6", type="general", tier=3, region="US-Central"),
        ]

        for agent_data in initial_agents:
            existing = await session.get(Agent, agent_data.agent_id)
            if not existing:
                new_agent = Agent.model_validate(agent_data)
                session.add(new_agent)
            else:
                existing.status = AgentStatus.AVAILABLE
                session.add(existing)

        await session.commit()
        logger.info("Initialized dummy agent data to DB.")

    yield


app = FastAPI(lifespan=lifespan)
app.include_router(router)