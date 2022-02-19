# kong-kafka-upstream-downstream

This repo consists of two [Kong](https://konghq.com/kong/) [plugins](https://docs.konghq.com/gateway/2.7.x/plugin-development/) that transform a request hitting the upstream server and transforms it on the way back down to the downstream server.

The two plugins are:

1. custom_kafka_producer
2. custom_kafka_consumer

Both plugins utilize [confluent_kafka](https://github.com/confluentinc/confluent-kafka-python) to produce and consume the messages.

### Before you start

Learn more about:

1. [Kafka](https://kafka.apache.org/intro)
2. [Kong API Gateway Plugin Development](https://docs.konghq.com/gateway/2.7.x/plugin-development/)

It is possible that only an Kong Enterprise allows enabling custom plugins.
If not, then [Konga](https://github.com/pantsel/konga) is an alternative that might reveal hidden custom plugins.

### Context

The plugin was developed to solve a design issue between:

1. Clients that communicate through APIs.
2. An event driven microservice archeticure, let's call them "internal services".

For clients to integrate with the **internal services**, they go through an API Gateway, Kong.

Clients communicate with Kong through API.
While Kong communicates with internal services using Kafka.

Since Kafka is event driven (and follows asynchronous protocol by nature), responses aren't expected to be returned, they can either be aggregated once they're ready to a certain topic, or a callback URL can be given to send the responses back to.
However, clients in this scenario need their responses back in one round-trip.

Hence, these plugins.

### How it Works

The `custom_kafka_producer` plugin takes the incoming request, attaches a `correlation-id` to it, and produces it to the desired Topic.

Once the message is produced to the upstream sever, the `custom_kafka_consumer` plugin consumes continuously from a consumer topic until a timeout is reached.
If the conusmer finds a message with a matching `correlation-id` to the request `correlation-id`, then the response is returned.
If not, an error is raised. (these particular cases can be handled differently and are subject to change).

### Setup locally

The `docker-compose.yml` file contains the following services: Kafka, Zookeeper, and Kong configuration.

The `.env` contains the following environment variables:

```
# Compose setup
COMPOSE_PROJECT_NAME=kong

# KONG DB Setup
KONG_PG_USER=kong
KONG_PG_PASSWORD=kong
KONG_PG_DB=kong
KONG_PG_HOST=kong-database
```

Run the project:

- `docker-compose build`
- `docker-compose up -d`

### Test the plugins locally

1. Visit http://localhost:8002 and login with your `kong_admin` credentials if Kong Enterprise is enabled.
2. Setup your first service, then create a route.
3. Add the following plugins for the route that has been created: `custom_kafka_producer` and `custom_kafka_consumer`.
4. The proxy is available at http://localhost:8000/, Hit the URI that was created in your route.
