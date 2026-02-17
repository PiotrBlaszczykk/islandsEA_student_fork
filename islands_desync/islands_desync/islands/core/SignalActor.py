import asyncio

import ray


@ray.remote(num_cpus=1)
class SignalActor:
    def __init__(self, required_number: int):
        self.required_number: int = required_number
        self.current_number: int = 0
        self.ready_event = asyncio.Event()
        self.finish_event = asyncio.Event()

    def send(self, event_type="start"):
        self.current_number += 1

        event = self.load_event(event_type)

        if self.current_number == self.required_number:
            self.current_number = 0
            event.set()

    async def wait(self, event_type="start"):
        event = self.load_event(event_type)

        await event.wait()

    def load_event(self, event_type) -> asyncio.Event:
        if event_type == "start":
            event = self.ready_event
        else:
            event = self.finish_event
        return event

