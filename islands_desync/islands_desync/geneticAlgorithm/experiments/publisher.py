import time

import pika

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))

# Create normal 'Hello World' type channel.
channel = connection.channel()
channel.confirm_delivery()
channel.queue_delete(f"hello")
channel.queue_declare(queue="hello")
#
# # We need to bind this channel to an exchange, that will be used to transfer
# # messages from our delay queue.
channel.queue_bind(exchange="amq.direct", queue="hello")

# Create our delay channel.
delay_channel = connection.channel()
delay_channel.confirm_delivery()

# This is where we declare the delay, and routing for our delay channel.

# island = 0
# for i in range(0, 5):
#     channel.queue_declare(queue=f'island-{i}')
#
# for i in range(0, 5):
#     channel.queue_bind(exchange='amq.direct',
#                    queue=f'island-{i}')
#

# for i in range(0, 5):
#     delay_channel.queue_declare(queue=f'island-from-{island}-to-{i}', arguments={
#         'x-message-ttl': i*1000+1000,  # Delay until the message is transferred in milliseconds.
#         'x-dead-letter-exchange': 'amq.direct',  # Exchange used to transfer the message from A to B.
#         'x-dead-letter-routing-key': f'island-{i}'  # Name of the queue we want the message transferred to.
#     })


def publish():
    dest = 2

    for i in range(0, 10):
        channel.basic_publish(
            exchange="",
            routing_key=f"hello",
            body=f"test {i}, time={time.time()}",
            properties=pika.BasicProperties(delivery_mode=2),
        )
        print(f"sent {i}")
        time.sleep(1)

    print(" [x] Sent")


if __name__ == "__main__":
    publish()
