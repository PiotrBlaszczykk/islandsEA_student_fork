import json

import pika

conf_file = "../algorithm/configurations/algorithm_configuration.json"

connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
channel = connection.channel()
delay_channel = connection.channel()


with open(conf_file) as file:
    configuration = json.loads(file.read())

rabbitmq_delays = configuration["island_delays"]
number_of_islands = configuration["number_of_islands"]


def remove_queues():
    for island in range(0, 10):
        channel.queue_delete(queue=f"island-{island}")
        for i in range(0, 10):
            channel.queue_delete(f"island-from-{island}-to-{i}")


def create_queues():
    for island in range(0, number_of_islands):
        queue_name = f"island-{island}"
        channel.queue_declare(queue=queue_name)
        for i in range(0, number_of_islands):
            if i != island:
                if rabbitmq_delays[str(island)][i] == -1:
                    continue
                try:
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
                except IndexError as e:
                    print("Create queues failed")
                    print(f"Invalid island delays configuration: {e}")
                    print(
                        f" Number of islands is {number_of_islands}, island 1 index: {island}, island 2 index: {i}"
                    )
                    exit(1)

    connection.close()


remove_queues()
create_queues()
