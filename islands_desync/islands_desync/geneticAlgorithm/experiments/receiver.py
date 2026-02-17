import json
import time

import pika
from jmetal.core.solution import FloatSolution

connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
channel = connection.channel()


def on_message(channel, method_frame, header_frame, body):
    print(body)
    print(method_frame.delivery_tag)
    # print(body)
    data_str = body.decode("utf-8")
    data = json.loads(data_str)
    float_solution = FloatSolution(
        data["lower_bound"],
        data["upper_bound"],
        data["number_of_variables"],
        data["number_of_objectives"],
    )
    float_solution.objectives = data["objectives"]
    float_solution.variables = data["variables"]
    float_solution.number_of_constraints = data["number_of_constraints"]
    print(float_solution.__str__())

    channel.basic_ack(delivery_tag=method_frame.delivery_tag)


def prepare(island_num):
    print(f"ISLAND {island_num}")
    while True:
        method, properties, body = channel.basic_get(queue=f"hello", auto_ack=True)
        print("body-------------------")
        print(body)
        print("-------------------body")
        time.sleep(10)


#
# def consume(island_num):
#     num_of_consumed = 0
#     queue_state = channel.queue_declare(queue=f'hello', passive=True)
#     queue_empty = queue_state.method.message_count == 0
#     while True:
#         if not queue_empty:
#             print(f"Number of messages {queue_state.method.message_count}")
#             num_of_consumed += 1
#             channel.basic_consume(f'island-{island_num}', on_message)
#             # method, properties, body = channel.basic_get(queue=f'hello', auto_ack=True)
#             # print(body)
#             time.sleep(10)

# try:
#     channel.start_consuming()
# except KeyboardInterrupt:
#     channel.stop_consuming()
# connection.close()


if __name__ == "__main__":
    prepare(1)
