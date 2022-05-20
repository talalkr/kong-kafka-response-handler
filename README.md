# kong-kafka-response-hanadler

This repo consists of two [Kong](https://konghq.com/kong/) [plugins](https://docs.konghq.com/gateway/2.7.x/plugin-development/) that transform a request hitting the upstream server and transforms it on the way back down from the downstream server.

The two plugins are:

1. custom_kafka_producer
2. custom_kafka_consumer

Both plugins utilize [confluent_kafka](https://github.com/confluentinc/confluent-kafka-python) to produce and consume the messages.
Also, [Kong's Correlation ID Plugin](https://docs.konghq.com/hub/kong-inc/correlation-id/) must run alongside these custom plugins in order to attach a correlation ID to each request going upstream.

### Before you start

Learn more about:

1. [Kafka](https://kafka.apache.org/intro)
2. [Kong API Gateway Plugin Development](https://docs.konghq.com/gateway/2.7.x/plugin-development/)

It is possible that only an Kong Enterprise allows enabling custom plugins.

### Context

The plugin was developed to solve a design issue between:

1. Clients that communicate with a API Gateway (Kong) using APIs
2. An event driven microservice archeticure, let's call it "internal services".

For clients to integrate with the **internal services**, they go through an API Gateway, Kong.

Clients communicate with Kong through API.
While Kong communicates with internal services using Kafka.

Since Kafka is event driven (and is an asynchronous protocol by nature), responses aren't expected to be returned, they can either be aggregated once they're ready to a certain topic, or a callback URL can be given to Kong, to send the responses back.
However, clients in this scenario need their responses back in one request-response.

The alternative is to use blocking and wait for a response received from a Kafka topic which is exactly what one of the plugins does.

### How it Works

A request is sent to Kong. The Correlation ID Plugin attaches a `correlation-id` to the request.

The `custom_kafka_producer` plugin takes the incoming request, moves its `correlation-id` to the request body, and produces it to the desired Topic as a message.

Once the message is produced to the upstream sever, the `custom_kafka_consumer` plugin consumes continuously from a consumer topic until a timeout is reached, like a blocking request.
While consuming, if the conusmer finds a message in the consumer topic with a matching `correlation-id` to the request `correlation-id`, then the response is returned. Otherwise, an error is raised.

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
