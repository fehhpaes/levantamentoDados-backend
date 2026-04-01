from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from typing import Optional
from loguru import logger

from app.core.config import settings

# MongoDB client instance
mongo_client: Optional[AsyncIOMotorClient] = None


async def connect_to_mongo():
    """Connect to MongoDB."""
    global mongo_client
    
    logger.info(f"Connecting to MongoDB...")
    
    mongo_client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        serverSelectionTimeoutMS=5000,
    )
    
    # Verify connection
    try:
        await mongo_client.admin.command('ping')
        logger.info("Successfully connected to MongoDB!")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close MongoDB connection."""
    global mongo_client
    
    if mongo_client:
        mongo_client.close()
        logger.info("MongoDB connection closed.")


async def init_db():
    """Initialize Beanie with document models."""
    from app.models import (
        Sport,
        League,
        Team,
        Match,
        Odds,
        Bookmaker,
        Prediction,
        User,
        Notification,
        NotificationPreferences,
        Webhook,
        BankrollState,
        BankrollTransaction,
    )
    
    if not mongo_client:
        await connect_to_mongo()
    
    await init_beanie(
        database=mongo_client[settings.MONGODB_DATABASE],
        document_models=[
            Sport,
            League,
            Team,
            Match,
            Odds,
            Bookmaker,
            Prediction,
            User,
            Notification,
            NotificationPreferences,
            Webhook,
            BankrollState,
            BankrollTransaction,
        ]
    )
    logger.info("Beanie ODM initialized with document models.")


def get_database():
    """Get MongoDB database instance."""
    if not mongo_client:
        raise RuntimeError("MongoDB client not initialized. Call connect_to_mongo() first.")
    return mongo_client[settings.MONGODB_DATABASE]
