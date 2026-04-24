import asyncio
import logging
from redis.asyncio import Redis

from services.prediction.config import get_prediction_settings
from services.prediction.context_assembly.assembler import ContextAssembler
from services.prediction.context_assembly.consumer import AnomalyAlertConsumer

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s %(module)s — %(message)s")
logger = logging.getLogger(__name__)

async def main():
    settings = get_prediction_settings()
    
    # Initialize Redis client
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    
    # Initialize Assembler
    assembler = ContextAssembler(redis_client=redis_client)
    
    # Initialize and start Consumer
    consumer = AnomalyAlertConsumer(settings=settings, assembler=assembler)
    await consumer.start()
    
    try:
        await consumer.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await consumer.stop()
        await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
