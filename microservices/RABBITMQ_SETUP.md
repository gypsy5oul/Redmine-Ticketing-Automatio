# RabbitMQ Message Queue Setup Guide

## Overview

RabbitMQ is included in the microservices stack for asynchronous communication between services. This enables event-driven architecture and decouples services for better scalability.

## Access RabbitMQ

- **AMQP Protocol**: `amqp://localhost:5672`
- **Management UI**: http://localhost:15672
- **Default Credentials**:
  - Username: `devops_user`
  - Password: `devops_password_change_this`

## Quick Start

### 1. Access Management UI

Open your browser and go to: http://localhost:15672

Login with:
- Username: `devops_user`
- Password: `devops_password_change_this`

### 2. Verify RabbitMQ is Running

```bash
# Check container status
docker ps | grep rabbitmq

# Check RabbitMQ health
docker exec devops-tickets-rabbitmq rabbitmq-diagnostics ping

# View RabbitMQ logs
docker logs devops-tickets-rabbitmq
```

## Use Cases for RabbitMQ in Microservices

### 1. Ticket Events

**Publisher**: Ticket Service
**Consumers**: Analytics Service, Notification Service

```
Ticket Created → Queue → [Analytics Update, Send Notifications]
```

### 2. SLA Breach Notifications

**Publisher**: SLA Service
**Consumers**: Escalation Service, Notification Service

```
SLA Breach → Queue → [Escalate Ticket, Notify Team Lead]
```

### 3. Team Member Updates

**Publisher**: Team Service
**Consumers**: Workload Service, Analytics Service

```
Member Status Change → Queue → [Recalculate Workload, Update Stats]
```

### 4. Work Session Events

**Publisher**: Work Session Service
**Consumers**: Analytics Service, Scheduling Service

```
Session End → Queue → [Update Analytics, Adjust Schedule]
```

## Python Integration Example

### Install Dependencies

```bash
pip install pika  # RabbitMQ client library
```

### Publisher Example (Send Message)

```python
import pika
import json
import os

# RabbitMQ connection
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST', 'localhost'),
        port=int(os.getenv('RABBITMQ_PORT', 5672)),
        credentials=pika.PlainCredentials(
            username=os.getenv('RABBITMQ_USER', 'devops_user'),
            password=os.getenv('RABBITMQ_PASSWORD', 'devops_password_change_this')
        )
    )
)

channel = connection.channel()

# Declare exchange
channel.exchange_declare(
    exchange='ticket_events',
    exchange_type='fanout',
    durable=True
)

# Publish message
message = {
    'event': 'ticket_created',
    'ticket_id': 123,
    'priority': 'high',
    'timestamp': '2025-01-15T10:30:00Z'
}

channel.basic_publish(
    exchange='ticket_events',
    routing_key='',
    body=json.dumps(message),
    properties=pika.BasicProperties(
        delivery_mode=2,  # Make message persistent
        content_type='application/json'
    )
)

print(f"Sent: {message}")
connection.close()
```

### Consumer Example (Receive Messages)

```python
import pika
import json
import os

# RabbitMQ connection
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST', 'localhost'),
        port=int(os.getenv('RABBITMQ_PORT', 5672)),
        credentials=pika.PlainCredentials(
            username=os.getenv('RABBITMQ_USER', 'devops_user'),
            password=os.getenv('RABBITMQ_PASSWORD', 'devops_password_change_this')
        )
    )
)

channel = connection.channel()

# Declare exchange
channel.exchange_declare(
    exchange='ticket_events',
    exchange_type='fanout',
    durable=True
)

# Declare queue
result = channel.queue_declare(queue='analytics_queue', durable=True)
queue_name = result.method.queue

# Bind queue to exchange
channel.queue_bind(exchange='ticket_events', queue=queue_name)

def callback(ch, method, properties, body):
    message = json.loads(body)
    print(f"Received: {message}")

    # Process the message
    if message['event'] == 'ticket_created':
        # Update analytics
        print(f"Processing ticket #{message['ticket_id']}")

    # Acknowledge message
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Start consuming
channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=queue_name, on_message_callback=callback)

print('Waiting for messages. Press CTRL+C to exit.')
channel.start_consuming()
```

## Common Exchange Types

### 1. Fanout (Broadcast)

All bound queues receive the message.

```python
channel.exchange_declare(
    exchange='ticket_events',
    exchange_type='fanout',
    durable=True
)
```

**Use Case**: Ticket created → notify all interested services

### 2. Direct (Routing Key)

Message goes to queues with matching routing key.

```python
channel.exchange_declare(
    exchange='priority_routing',
    exchange_type='direct',
    durable=True
)

# Publish with routing key
channel.basic_publish(
    exchange='priority_routing',
    routing_key='high_priority',
    body=message
)
```

**Use Case**: Route high-priority tickets differently

### 3. Topic (Pattern Matching)

Messages routed based on pattern matching.

```python
channel.exchange_declare(
    exchange='ticket_topic',
    exchange_type='topic',
    durable=True
)

# Routing keys: "ticket.created.high", "ticket.updated.low"
# Pattern: "ticket.*.high" matches all high priority tickets
```

**Use Case**: Subscribe to specific ticket patterns (e.g., all high priority)

### 4. Headers (Attribute Matching)

Route based on message headers.

```python
channel.exchange_declare(
    exchange='header_routing',
    exchange_type='headers',
    durable=True
)
```

**Use Case**: Complex routing based on multiple attributes

## Recommended Exchange Setup

### Create Exchanges via Management UI

1. Go to: http://localhost:15672/#/exchanges
2. Click "Add a new exchange"
3. Create these exchanges:

| Exchange Name | Type | Durable | Description |
|--------------|------|---------|-------------|
| ticket.events | fanout | Yes | All ticket events |
| sla.events | fanout | Yes | SLA breach events |
| team.events | fanout | Yes | Team member updates |
| analytics.events | fanout | Yes | Analytics triggers |

### Create Queues via Management UI

1. Go to: http://localhost:15672/#/queues
2. Click "Add a new queue"
3. Create these queues:

| Queue Name | Durable | Description |
|-----------|---------|-------------|
| analytics.ticket.queue | Yes | Analytics service consumes ticket events |
| notification.ticket.queue | Yes | Notification service consumes ticket events |
| escalation.sla.queue | Yes | Escalation service consumes SLA events |
| workload.team.queue | Yes | Workload service consumes team events |

## Integration with Microservices

### 1. Add RabbitMQ to Service Environment

Update `docker-compose.microservices.yml` (already done):

```yaml
environment:
  RABBITMQ_HOST: rabbitmq
  RABBITMQ_PORT: 5672
  RABBITMQ_USER: devops_user
  RABBITMQ_PASSWORD: devops_password_change_this
```

### 2. Add Dependency in Service

```yaml
depends_on:
  rabbitmq:
    condition: service_healthy
```

### 3. Create RabbitMQ Client Module

Save as `rabbitmq_client.py` in each service:

```python
import pika
import json
import os
from typing import Callable, Optional
from loguru import logger

class RabbitMQClient:
    def __init__(self):
        self.host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
        self.port = int(os.getenv('RABBITMQ_PORT', 5672))
        self.user = os.getenv('RABBITMQ_USER', 'devops_user')
        self.password = os.getenv('RABBITMQ_PASSWORD', 'devops_password_change_this')

    def get_connection(self):
        credentials = pika.PlainCredentials(self.user, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        return pika.BlockingConnection(parameters)

    def publish(self, exchange: str, message: dict, routing_key: str = ''):
        """Publish message to exchange"""
        try:
            connection = self.get_connection()
            channel = connection.channel()

            channel.exchange_declare(
                exchange=exchange,
                exchange_type='fanout',
                durable=True
            )

            channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent
                    content_type='application/json'
                )
            )

            logger.info(f"Published to {exchange}: {message}")
            connection.close()

        except Exception as e:
            logger.error(f"Failed to publish message: {e}")

    def consume(self, queue: str, exchange: str, callback: Callable):
        """Consume messages from queue"""
        try:
            connection = self.get_connection()
            channel = connection.channel()

            channel.exchange_declare(
                exchange=exchange,
                exchange_type='fanout',
                durable=True
            )

            channel.queue_declare(queue=queue, durable=True)
            channel.queue_bind(exchange=exchange, queue=queue)
            channel.basic_qos(prefetch_count=1)

            def wrapped_callback(ch, method, properties, body):
                try:
                    message = json.loads(body)
                    callback(message)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(queue=queue, on_message_callback=wrapped_callback)

            logger.info(f"Started consuming from {queue}")
            channel.start_consuming()

        except Exception as e:
            logger.error(f"Failed to consume messages: {e}")

# Global instance
rabbitmq = RabbitMQClient()
```

### 4. Use in Service

**Ticket Service (Publisher)**:

```python
from rabbitmq_client import rabbitmq

@app.post("/api/v1/tickets/")
async def create_ticket(ticket: TicketCreate):
    # Create ticket in database
    db_ticket = create_ticket_in_db(ticket)

    # Publish event
    rabbitmq.publish(
        exchange='ticket.events',
        message={
            'event': 'ticket_created',
            'ticket_id': db_ticket.id,
            'priority': db_ticket.priority,
            'timestamp': datetime.utcnow().isoformat()
        }
    )

    return db_ticket
```

**Analytics Service (Consumer)**:

```python
from rabbitmq_client import rabbitmq
import asyncio

def process_ticket_event(message: dict):
    logger.info(f"Processing ticket event: {message}")
    # Update analytics
    if message['event'] == 'ticket_created':
        update_ticket_analytics(message['ticket_id'])

# Start consumer in background
async def start_consumer():
    await asyncio.to_thread(
        rabbitmq.consume,
        queue='analytics.ticket.queue',
        exchange='ticket.events',
        callback=process_ticket_event
    )

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_consumer())
```

## Monitoring and Management

### View Queue Status

```bash
# List all queues
curl -u devops_user:devops_password_change_this \
  http://localhost:15672/api/queues

# Get specific queue info
curl -u devops_user:devops_password_change_this \
  http://localhost:15672/api/queues/%2F/analytics.ticket.queue
```

### View Messages in Queue (Peek)

Via Management UI:
1. Go to Queues tab
2. Click on queue name
3. Click "Get messages"
4. Set number of messages to peek
5. Click "Get Message(s)"

### Purge Queue (Clear All Messages)

```bash
curl -i -u devops_user:devops_password_change_this \
  -X DELETE http://localhost:15672/api/queues/%2F/analytics.ticket.queue/contents
```

## Best Practices

1. **Make Messages Persistent**: Set `delivery_mode=2` for important messages
2. **Use Durable Queues**: Ensure queues survive RabbitMQ restarts
3. **Acknowledge Messages**: Always ack/nack messages after processing
4. **Handle Failures**: Implement retry logic with exponential backoff
5. **Monitor Queue Depth**: Alert if queues grow too large
6. **Use Dead Letter Exchanges**: Handle failed messages gracefully
7. **Set Prefetch Count**: Limit concurrent message processing

## Troubleshooting

### RabbitMQ Not Starting

```bash
# Check logs
docker logs devops-tickets-rabbitmq

# Check disk space (RabbitMQ needs disk space)
df -h
```

### Connection Refused

```bash
# Verify RabbitMQ is listening
docker exec devops-tickets-rabbitmq netstat -tuln | grep 5672

# Test connection
docker exec devops-tickets-rabbitmq rabbitmq-diagnostics ping
```

### Messages Not Being Consumed

1. Check queue has consumers: http://localhost:15672/#/queues
2. Verify queue is bound to exchange
3. Check consumer logs for errors
4. Ensure messages are being published

### Queue Growing Too Large

1. Check if consumers are running
2. Check if consumers are acknowledging messages
3. Increase number of consumer instances
4. Optimize message processing time

## Production Considerations

1. **Clustering**: Set up RabbitMQ cluster for high availability
2. **Monitoring**: Use Prometheus exporter for RabbitMQ metrics
3. **Backups**: Regularly backup queue configurations
4. **Resource Limits**: Set memory and disk limits
5. **Security**: Change default passwords
6. **SSL/TLS**: Enable encryption for production
7. **Message TTL**: Set TTL to prevent old messages from accumulating

## Environment Variables

```bash
# In .env file (already configured)
RABBITMQ_USER=devops_user
RABBITMQ_PASSWORD=devops_password_change_this
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_MANAGEMENT_PORT=15672
```

## Useful Commands

```bash
# Check RabbitMQ status
docker exec devops-tickets-rabbitmq rabbitmqctl status

# List all queues
docker exec devops-tickets-rabbitmq rabbitmqctl list_queues

# List all exchanges
docker exec devops-tickets-rabbitmq rabbitmqctl list_exchanges

# List all bindings
docker exec devops-tickets-rabbitmq rabbitmqctl list_bindings

# Add user
docker exec devops-tickets-rabbitmq rabbitmqctl add_user newuser password

# Set permissions
docker exec devops-tickets-rabbitmq rabbitmqctl set_permissions -p / newuser ".*" ".*" ".*"
```

## Next Steps

1. ✅ Access Management UI at http://localhost:15672
2. 🔧 Create exchanges for your use cases
3. 🔧 Create queues and bind to exchanges
4. 🔧 Add RabbitMQ client to microservices
5. 🔧 Implement publishers in relevant services
6. 🔧 Implement consumers in relevant services
7. 🔧 Test message flow end-to-end

---

**RabbitMQ Setup Complete!** 🐰

Message queue ready for asynchronous microservices communication.
