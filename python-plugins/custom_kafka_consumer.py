#!/usr/bin/env python3
import json
from os import path
import logging
from uuid import UUID
import kong_pdk.pdk.kong as kong
from kong_pdk.cli import start_dedicated_server
from confluent_kafka import Consumer

# setup logging
log_file_path = path.join(path.dirname(path.abspath(__file__)), "logging.conf")
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    filename=log_file_path,
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Set up environment variables to be used in custom plugins
BOOTSTRAP_SERVER = "kafka:9092"
KAFKA_FEEDBACK_TOPIC = "feedback"

Schema = ()
version = "0.1.0"
priority = 0

# message store key -> correlation-id, value -> message
messages_store = {}

consumer = Consumer(
    {
        "bootstrap.servers": BOOTSTRAP_SERVER,
        "group.id": "test-group",
        "auto.offset.reset": "latest",
        "enable.auto.commit": "true",
    }
)
consumer.subscribe([KAFKA_FEEDBACK_TOPIC])
logging.info("Consumer is running...")


class Plugin(object):
    """
    This plugin consumes messages that match the given correlation ID
    The topic is the feedback topic.
    """

    def __init__(self, config):
        self.config = config

    def fetch_and_remove_from_store(self, correlation_id: UUID) -> dict:
        stored_message = messages_store.get(correlation_id)

        if stored_message:
            del messages_store[correlation_id]

        return stored_message

    def add_message_to_store(self, message_correlation_id: str, message: dict) -> None:
        """
        Adds messages found in the stream to the store, these are messages
        that don't match the current request correlation ID
        """
        logging.info(f"4. Adding message to store {message}")
        messages_store[message_correlation_id] = message

    def fetch_response_message(
        self, request_correlation_id: str, messages: list
    ) -> dict:
        """
        Iterates messages that came from the stream
        :returns: the message with a matching correlation id in the kong request, otherwise None
        """
        # TOOD: must use message.error() on each message
        response_message = None

        for message in messages:
            # decoded_message = ast.literal_eval(message.value().decode("utf-8"))
            decoded_message = str(message.value().decode("utf-8")).replace("'", '"')
            if type(decoded_message) == str:
                decoded_message = json.loads(decoded_message)

            message_correlation_id = decoded_message.get("correlation-id")
            logging.info(
                f"{request_correlation_id} == {message_correlation_id} is {request_correlation_id == message_correlation_id}"
            )

            if request_correlation_id == message_correlation_id:
                response_message = decoded_message
            else:
                self.add_message_to_store(
                    message_correlation_id=message_correlation_id,
                    message=decoded_message,
                )

        return response_message

    def iterative_consume(
        self,
        request_correlation_id: str,
        num_of_iterations: int,
        consume_timeout: float,
    ):
        """
        Consumes Kafka messages with a timeout, this happens based on the `num_of_iterations`
        If messages are found, they are added to the store
        If a response message is found, i.e. correlation_id matches the request correlation_id,
            Then it is returned right away

        Iteration Example:
            if consume_timeout = 0.04 and num_of_iterations = 25
            Then the consumer will run every 40ms until a message is found, if none is found
            Then it timeout after 1 second since 0.04 (ms) * 25 (iterations) = 1 second
        """
        i = 0
        response_message = None

        while i < num_of_iterations:
            messages = consumer.consume(5, timeout=consume_timeout)

            if not messages:
                stored_message = self.fetch_and_remove_from_store(
                    request_correlation_id
                )
                if stored_message:
                    return stored_message

                logging.error(f"no messages found by consumer in iteration{i}")
                i += 1
                continue

            response_message = self.fetch_response_message(
                request_correlation_id, messages
            )
            if response_message:
                break

            i += 1

        return response_message

    def response(self, kong: kong.kong):
        """Consume the message from the Kafka message broker and return it as the response body"""
        correlation_id = kong.request.get_header("Kong-Request-ID")[0]

        stored_message = self.fetch_and_remove_from_store(correlation_id)
        if stored_message:
            logging.info(f"SUCCESS fetched stored message {stored_message}")
            return kong.response.exit(200, stored_message)

        # Consume messages for a maximum of 1 second
        decoded_message = self.iterative_consume(
            request_correlation_id=correlation_id,
            num_of_iterations=25,
            consume_timeout=0.04,
        )
        if decoded_message:
            logging.info(f"SUCCESS consumer found the message {decoded_message}")
            return kong.response.exit(200, decoded_message)

        logging.error(f"FAILURE with correlation-id {correlation_id}")
        return kong.response.exit(400, {"message": "failed to get message"})


# use the embedded server to run each plugin as a microservice
if __name__ == "__main__":
    from kong_pdk.cli import start_dedicated_server

    start_dedicated_server("custom_kafka_consumer", Plugin, version, priority, Schema)
