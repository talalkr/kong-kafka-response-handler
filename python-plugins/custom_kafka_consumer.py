#!/usr/bin/env python3
import ast
from os import path, environ
import logging

from ksql import KSQLAPI
import kong_pdk.pdk.kong as kong
from kong_pdk.cli import start_dedicated_server

# setup logging
log_file_path = path.join(path.dirname(path.abspath(__file__)), "logging.conf")
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    filename=log_file_path,
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)

KAFKA_BOOTSTRAP_SERVER = environ.get("KAFKA_BOOTSTRAP_SERVER")
KAFKA_FEEDBACK_TOPIC = environ.get("KAFKA_FEEDBACK_TOPIC")
ROW_QUERY_INDEX = 1

Schema = ()
version = "0.1.0"
priority = 0


# KSQL
ksql_client = KSQLAPI(environ.get("KSQL_URL"))

# -- Create stream if it doesn't exist
ksql_client.ksql(
    f"""
        CREATE STREAM IF NOT EXISTS message (
            correlation_id STRING,
            message STRING
        ) WITH (
            KAFKA_TOPIC = '{KAFKA_FEEDBACK_TOPIC}',
            KEY_FORMAT = 'NONE',
            VALUE_FORMAT = 'JSON'
        )
    """
)


class Plugin(object):
    """
    This plugin consumes messages that match the given correlation ID
    The topic is the feedback topic.
    """

    def __init__(self, config):
        self.config = config

    def get_query_response(self, query) -> list:
        """Loop through KSQL DB Query response and combine message parts to retrieve complete message"""
        full_message = ""

        try:
            for resp in query:
                full_message = f"{full_message}{resp}"
        except Exception as e:
            logging.error(e)

        return full_message

    def get_message_by_correlation_id(self, correlation_id: str) -> None:
        """Query KSQL DB to retrieve kafka message by correlation_id"""
        query = ksql_client.query(
            f"""
            SELECT * FROM message WHERE correlation_id = '{correlation_id}'
            """
        )

        message = self.get_query_response(query)
        message_list = ast.literal_eval(message)

        correlation_id, message = message_list[ROW_QUERY_INDEX].get("row").get("columns")
        return message

    def response(self, kong: kong.kong):
        """Consume the message from the Kafka message broker and return it as the response body"""
        correlation_id = kong.request.get_header("Kong-Request-ID")[0]

        decoded_message = self.get_message_by_correlation_id(correlation_id=correlation_id)
        if decoded_message:
            logging.info(f"successfully consumed message with correlation_id {correlation_id} consumed from stream")
            return kong.response.exit(200, decoded_message)

        logging.error(f"failed to retrieve message with correlation_id {correlation_id}")
        return kong.response.exit(400, {"message": "failed to get message"})


# use the embedded server to run each plugin as a microservice
if __name__ == "__main__":
    from kong_pdk.cli import start_dedicated_server

    start_dedicated_server("custom_kafka_consumer", Plugin, version, priority, Schema)
