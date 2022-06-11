# kong-kafka-response-hanadler

This repo consists of two [Kong](https://konghq.com/kong/) [plugins](https://docs.konghq.com/gateway/2.7.x/plugin-development/) that transform a request hitting the upstream server and transforms it on the way back down from the downstream server.

The two plugins are:

1. custom_kafka_producer
2. custom_kafka_consumer

The `custom_kafka_producer` plugin utilizes [confluent_kafka](https://github.com/confluentinc/confluent-kafka-python) to produce messages.
The `custom_kafka_consumer` plugin runs a [ksql client](https://github.com/bryanyang0528/ksql-python) that subscribes to a `KAFKA_FEEDBACK_TOPIC` and creates a stream.
[Kong's Correlation ID Plugin](https://docs.konghq.com/hub/kong-inc/correlation-id/) must run alongside these custom plugins in order to attach a correlation ID to each request going upstream.

### Before you start

Learn more about:

1. [Kong API Gateway Plugin Development](https://docs.konghq.com/gateway/2.7.x/plugin-development/)
2. [Kafka](https://kafka.apache.org/intro)
3. [KSQLDB](https://ksqldb.io/)
4. [KSQL-Python](https://github.com/bryanyang0528/ksql-python)

It is possible that only Kong **Enterprise** allows enabling custom plugins.

### Context

The plugin was developed to solve a design issue between:

1. Clients that communicate with a API Gateway (Kong) using APIs
2. An event driven microservice archeticure, let's call it "internal services".

For clients to integrate with the **internal services**, they go through an API Gateway, Kong.

Clients communicate with Kong through API.
While Kong communicates with internal services using Kafka.

Since Kafka is event driven (and is an asynchronous protocol by nature), responses aren't expected to be returned, they can either be aggregated once they're ready to a certain topic, or a callback URL can be given to Kong, to send the responses back.
However, clients in this scenario need their responses back in one request-response.

The alternative is to wait for a response received from a Kafka topic which is exactly what one of the plugins does.

### How it Works

A request is sent to Kong. The Correlation ID Plugin attaches a `correlation_id` to the request. The `custom_kafka_producer` plugin takes the incoming request, moves its `correlation_id` to the request body, and produces it to the desired Topic as a message.

Once the message is produced to the upstream sever, the `custom_kafka_consumer` plugin retrieves the message by `corrrelation_id` from KSQL DB until timeout is reached. The KSQL stream is able to find the message since it has been configured to subscribe to the kafka feedback topic. Once the message is retrieved it is returned to the client.

### Setup locally

The `docker-compose.yml` file contains the following services: KSQLDB-Server, Schema-Registry, Kafka, Zookeeper, and a Kong configuration with the postgres DB.

The following `.env` variables are required:

```
# Compose setup
COMPOSE_PROJECT_NAME=kong

# KONG DB Setup
KONG_PG_USER=kong
KONG_PG_PASSWORD=kong
KONG_PG_DB=kong
KONG_PG_HOST=kong-database

# Kong
KONG_DATABASE=postgres
KONG_PASSWORD=kongkong

# Kong Enterprise Configuration
KONG_ENFORCE_RBAC='off'
KONG_PORTAL='off'
KONG_VITALS='off'

# Kafka
KAFKA_BOOTSTRAP_SERVER="kafka:9092"
KAFKA_FEEDBACK_TOPIC="kong.feedback"

# KSQL
KSQL_URL="http://ksqldb-server:8088"

# If you wish to enable enterprise, fill these values
KONG_ENFORCE_RBAC='on'
KONG_PORTAL='on'
KONG_VITALS='on'
KONG_ADMIN_GUI_SESSION_CONF=''
KONG_ADMIN_GUI_AUTH=basic-auth
KONG_PORTAL_AUTH=basic-auth
KONG_PORTAL_SESSION_CONF=''
KONG_LICENSE_DATA=''
```

Run the project:

- `docker-compose build`
- `docker-compose up -d`

### Test the plugins locally

Run this [Faust app](https://github.com/talalkr/faust-app) or any backend service alongside the response handler that consumes and produces Kafka messages from this API Gateway.

1. Visit http://localhost:8002 and login to Kong Manager with the `kong_admin` credentials.
2. Configure the Kong service to hit this [Faust app](https://github.com/talalkr/faust-app), then create a route.
3. Add the following plugins for the route that has been created: `custom_kafka_producer` and `custom_kafka_consumer`.
4. The proxy is available at http://localhost:8000/, Hit the URI that was created in your route.
