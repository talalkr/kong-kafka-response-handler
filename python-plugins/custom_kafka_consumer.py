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
KAFKA_FEEDBACK_TOPIC = "kong.feedback"

Schema = ({"max_timeout": {"type": "number", "default": 1, "required": True}},)

version = "0.1.0"
priority = 0

# message store:
#   key -> correlation-id
#   value -> message
messages_store = {}


# Kafka Consumer
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
        max_timeout = self.config.get("max_timeout")

        self.num_of_iterations = max_timeout * 25
        self.consume_timeout = 0.04  # intentionally small to reduce blocking time
        self.num_of_messages = 10  # depends on the consume_timeout

    def fetch_and_remove_from_store(self, correlation_id: UUID) -> dict:
        stored_message = messages_store.get(correlation_id)

        if stored_message:
            del messages_store[correlation_id]

        return stored_message

    def add_message_to_store(self, message_correlation_id: str, message: dict) -> None:
        logging.info(
            f"Added message with correlation-id {message_correlation_id} to the store"
        )
        messages_store[message_correlation_id] = message

    def extract_messages(self, messages: list) -> None:
        """Extracts messages from stream and adds them to the store"""
        for message in messages:
            try:
                message.error()
            except Exception as error:
                logging.error(error)

            decoded_message = str(message.value().decode("utf-8")).replace("'", '"')

            if type(decoded_message) == str:
                decoded_message = json.loads(decoded_message)

            self.add_message_to_store(
                message_correlation_id=decoded_message.get("correlation-id"),
                message=decoded_message,
            )

    def iterative_consume(
        self,
        correlation_id: str,
        num_of_messages: int,
        num_of_iterations: int,
        consume_timeout: float,
    ) -> None:
        """
        :param num_of_messages (int): the number of messages to consume from the kafka stream in one iteration
        :param num_of_iterations (int): the number of iterations to call consume()
        :param consume_timeout (float): the maximum amount of time the consumer must wait if no messages were found while consuming

        Iteration Example:
            assume consume_timeout = 0.04 and num_of_iterations = 25
            the consumer consumes 50 messages before it reaches the timeout of 40 ms, it repeats that 25 times
            Total wait time is 40 (ms) * 25 (iterations) = 1 second
        """
        stored_message = None

        for _ in range(num_of_iterations):
            messages = consumer.consume(num_of_messages, timeout=consume_timeout)

            if messages:
                self.extract_messages(messages)

            stored_message = self.fetch_and_remove_from_store(correlation_id)
            if stored_message:
                break

        return stored_message

    def response(self, kong: kong.kong):
        """Consume the message from the Kafka message broker and return it as the response body"""
        correlation_id = kong.request.get_header("Kong-Request-ID")[0]

        decoded_message = self.iterative_consume(
            correlation_id=correlation_id,
            num_of_messages=self.num_of_messages,
            num_of_iterations=self.num_of_iterations,
            consume_timeout=self.consume_timeout,
        )
        if decoded_message:
            logging.info(
                f"successfully consumed message with correlation-id {correlation_id} consumed from stream"
            )
            return kong.response.exit(200, decoded_message)

        stored_message = self.fetch_and_remove_from_store(correlation_id)
        if stored_message:
            logging.info(
                f"successfully retrieved cached message with correlation-id {correlation_id}"
            )
            return kong.response.exit(200, stored_message)

        logging.error(
            f"failed to retrieve message with correlation-id {correlation_id}"
        )
        return kong.response.exit(400, {"message": "failed to get message"})


# use the embedded server to run each plugin as a microservice
if __name__ == "__main__":
    from kong_pdk.cli import start_dedicated_server

    start_dedicated_server("custom_kafka_consumer", Plugin, version, priority, Schema)
