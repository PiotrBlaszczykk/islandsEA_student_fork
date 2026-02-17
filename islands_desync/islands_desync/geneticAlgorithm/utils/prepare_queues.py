import json
import time

import pika


def try_connection(conf_file):
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
            if connection.is_open:
                print("OK")

                channel = connection.channel()
                delay_channel = connection.channel()

                with open(conf_file) as file:
                    configuration = json.loads(file.read())

                rabbitmq_delays = configuration["island_delays"]

                remove_queues(channel)
                create_queues(connection, channel, delay_channel, rabbitmq_delays)
                connection.close()
                exit(0)
        except Exception as error:
            print("No connection yet:", error.__class__.__name__)
            time.sleep(5)


def remove_queues(channel):
    for island in range(0, 5):
        channel.queue_delete(queue=f"island-{island}")
        for i in range(0, 5):
            channel.queue_delete(f"island-from-{island}-to-{i}")


def create_queues(connection, channel, delay_channel, rabbitmq_delays):
    for island in range(0, 3):
        queue_name = f"island-{island}"
        channel.queue_declare(queue=queue_name)
        for i in range(0, 3):
            if i != island:
                delay_channel.queue_declare(
                    queue=f"island-from-{island}-to-{i}",
                    arguments={
                        "x-message-ttl": rabbitmq_delays[str(island)][
                            i
                        ],  # Delay until the message is transferred in milliseconds.
                        "x-dead-letter-exchange": "amq.direct",  # Exchange used to transfer the message from A to B.
                        "x-dead-letter-routing-key": f"island-{i}",  # Name of the queue we want the message transferred to.
                    },
                )

    connection.close()


if __name__ == "__main__":
    try_connection("../algorithm/configurations/algorithm_configuration.json")
