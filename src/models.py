import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import TIMESTAMP


# ENUMS
class AgentStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"

class LeadStatus(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"


# AGENT MODELS
class AgentBase(SQLModel):
    type: str = Field(default=None)
    tier: int = Field(default=1, ge=1, le=5)
    region: str = Field(default="US-West")
    language: str = Field(default="EN")
    last_used: Optional[datetime] = Field(default=None)

class Agent(AgentBase, table=True):
    __tablename__ = "agents"
    agent_id: str = Field(primary_key=True)
    status: AgentStatus = Field(default=AgentStatus.AVAILABLE)

class AgentCreate(AgentBase):
    agent_id: str


# LEAD MODELS
class LeadBase(SQLModel):
    type: str = Field(default="general")
    min_tier: int = Field(default=1, ge=1, le=5)
    region: str = Field(default="US-West")
    language: str = Field(default="EN")

class Lead(LeadBase, table=True):
    __tablename__ = "leads"
    lead_id: str = Field(
        default_factory=lambda: f"lead_{uuid.uuid4().hex[:8]}", 
        primary_key=True
    )
    status: LeadStatus = Field(default=LeadStatus.PENDING)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        sa_type=TIMESTAMP(timezone=False)
    )

class LeadCreate(LeadBase):
    pass