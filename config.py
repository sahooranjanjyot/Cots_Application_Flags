import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 1. Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://qdvi_user:qdvi_password@localhost:5432/qdvi_engine")
    
    # 2. FLAGS Endpoint
    FLAGS_ENDPOINT = os.getenv("FLAGS_ENDPOINT", "http://localhost:8000/flags/api/v1/quality")
    FLAGS_TIMEOUT_MS = int(os.getenv("FLAGS_TIMEOUT_MS", "5000"))
    MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
    RETRY_BACKOFF_STRATEGY = os.getenv("RETRY_BACKOFF_STRATEGY", "EXPONENTIAL") # EXPONENTIAL or FIXED
    
    # 3. RabbitMQ
    RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    QUEUE_NAME = os.getenv("QUEUE_NAME", "qdvi_flags_queue")
    
    # 4. Security
    API_KEY = os.getenv("API_KEY", "prod-secure-key-12345")
    
    # 5. Backup & Retention
    EVENT_RETENTION_DAYS = int(os.getenv("EVENT_RETENTION_DAYS", "30"))

settings = Config()
