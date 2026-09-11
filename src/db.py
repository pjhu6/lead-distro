import os
from collections.abc import AsyncGenerator
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://postgres:password@localhost:5432/leads_db"
)

engine = create_async_engine(
    DATABASE_URL, 
    echo=False, 
    pool_size=20, 
    max_overflow=10
)

AsyncSessionLocal = async_sessionmaker(
    engine, 
    expire_on_commit=False, 
    class_=AsyncSession
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def init_db() -> None:
    raw_dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(raw_dsn)
    try:
        # Just for demo purposes, drop all persisted data on restart.
        await conn.execute("DROP TABLE IF EXISTS leads CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS agents CASCADE;")
        await conn.execute("DROP TYPE IF EXISTS agentstatus CASCADE;")
        await conn.execute("DROP TYPE IF EXISTS leadstatus CASCADE;")

        await conn.execute("CREATE TYPE agentstatus AS ENUM ('AVAILABLE', 'BUSY', 'OFFLINE');")
        await conn.execute("CREATE TYPE leadstatus AS ENUM ('PENDING', 'ASSIGNED');")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                lead_id TEXT PRIMARY KEY,
                type TEXT,
                min_tier INTEGER,
                region TEXT DEFAULT 'US-West',
                language TEXT DEFAULT 'EN',
                status leadstatus DEFAULT 'PENDING'::leadstatus,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                type TEXT,
                tier INTEGER,
                region TEXT DEFAULT 'US-West',
                language TEXT DEFAULT 'EN',
                last_used TIMESTAMPTZ,
                status agentstatus DEFAULT 'AVAILABLE'::agentstatus
            )
        """)
        
        # Create index on fields we will match on
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agents_available_matching 
            ON agents (type, region, tier, language, last_used ASC NULLS FIRST) 
            WHERE status = 'AVAILABLE'::agentstatus
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_leads_pending_queue 
            ON leads (type, region, min_tier, language, created_at ASC) 
            WHERE status = 'PENDING'::leadstatus
        """)
    finally:
        await conn.close()