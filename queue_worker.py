import json
import logging
import time
import httpx
import pika
from circuitbreaker import circuit
from config import settings

logger = logging.getLogger("queue_worker")
logger.setLevel(logging.INFO)

# Setup Circuit Breaker
@circuit(failure_threshold=5, recovery_timeout=30)
def send_to_flags(payload: dict):
    from config import settings
    # Real payload to flags endpoint
    timeout = settings.FLAGS_TIMEOUT_MS / 1000.0
    try:
        response = httpx.post(
            settings.FLAGS_ENDPOINT, 
            json=payload, 
            timeout=timeout
        )
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            logger.error(f"FLAGS 5xx error: {exc}")
            raise # Circuit breaker counts this as failure
        else:
            logger.error(f"FLAGS 4xx error (non-retriable): {exc}")
            # 4xx errors shouldn't trip circuit breaker endlessly
            return exc.response
    except Exception as exc:
        logger.error(f"FLAGS Integration failure: {exc}")
        raise

def process_message(ch, method, properties, body):
    payload = json.loads(body)
    event_id = payload.get("eventId")
    
    attempts = 0
    max_attempts = settings.MAX_RETRY_ATTEMPTS
    
    while attempts < max_attempts:
        try:
            logger.info(f"Sending event {event_id} to FLAGS, attempt {attempts+1}")
            response = send_to_flags(payload)
            
            if response.status_code >= 400 and response.status_code < 500:
                logger.error(f"Event {event_id} permanently failed with 4xx: {response.text}")
                # We do not retry 4xx errors
                ch.basic_ack(delivery_tag=method.delivery_tag)
                # Here we could record to DB via API or direct
                return
            
            logger.info(f"Event {event_id} successfully sent to FLAGS")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            # Update DB to SUCCESS via some DB method
            return
            
        except Exception as e:
            attempts += 1
            if attempts >= max_attempts:
                logger.error(f"Event {event_id} failed after {max_attempts} attempts. Pushing to DLQ or dead-letter")
                # Need to update DB tracking manually here
                ch.basic_ack(delivery_tag=method.delivery_tag) # we consumed it but it failed permanently
                return
            
            # Backoff
            backoff = (2 ** attempts) if settings.RETRY_BACKOFF_STRATEGY == "EXPONENTIAL" else 5
            logger.warning(f"Failed. Retrying in {backoff} seconds...")
            time.sleep(backoff)

def start_worker():
    import time
    connection = None
    for _ in range(5):
        try:
            connection = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
            break
        except Exception as e:
            logger.warning(f"RabbitMQ not ready: {e}. Retrying in 5s...")
            time.sleep(5)
            
    if not connection:
        logger.error("Could not connect to RabbitMQ.")
        return

    channel = connection.channel()
    channel.queue_declare(queue=settings.QUEUE_NAME, durable=True)
    
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=settings.QUEUE_NAME, on_message_callback=process_message)
    
    logger.info("Worker started. Waiting for messages.")
    channel.start_consuming()

if __name__ == "__main__":
    start_worker()
