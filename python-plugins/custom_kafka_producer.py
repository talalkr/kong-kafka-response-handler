#!/usr/bin/env python3
from os import path
import logging
import kong_pdk.pdk.kong as kong
from confluent_kafka import Producer


# setup logging
log_file_path = path.join(path.dirname(path.abspath(__file__)), "logging.conf")
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    filename=log_file_path,
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Kong Plugin Config
Schema = ({"kafka_topic": {"type": "string", "required": True}},)
version = "0.1.0"
priority = 0


# Kafka Set up environment variables to be used in custom plugins
BOOTSTRAP_SERVER = "kafka:9092"


class Plugin(object):
    """
    This plugin takes each request body from Kong and produces it to Kafka when heading upstream.
    """

    def __init__(self, config):
        self.config = config
        self.producer = Producer(
            {
                "bootstrap.servers": BOOTSTRAP_SERVER,
            }
        )
        logging.info("Producer is running...")

    def delivery_report(self, err, msg):
        """Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush()."""
        try:
            if err is not None:
                logging.error(f"Message delivery failed: {err}")
            else:
                logging.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")
        except Exception as err:
            logging.error(f"Exception dr: {err}")

    def access(self, kong: kong.kong):
        """Produce the request body into a Kafka Topic received from the Schema"""
        try:
            body, err = kong.request.get_body()
            body["correlation-id"] = kong.request.get_header("Kong-Request-ID")[0]

            body_replaced_single_quotes = str(body).replace("'", '"')
            body_encoded = body_replaced_single_quotes.encode("utf-8")

            self.producer.poll(0)
            # Asynchronously produce a message, the delivery report callback
            # will be triggered from poll() below when the message has
            # been successfully delivered or failed permanently.
            self.producer.produce(
                self.config.get("kafka_topic"),
                body_encoded,
                callback=self.delivery_report,
            )
            self.producer.flush()

            logging.info(f"Sent request with correlation-id: {body['correlation-id']}")

        except Exception as err:
            logging.error(f"Exception: {err}")
            return


# use the embedded server to run each plugin as a microservice
if __name__ == "__main__":
    from kong_pdk.cli import start_dedicated_server

    start_dedicated_server("custom_kafka_producer", Plugin, version, priority, Schema)
