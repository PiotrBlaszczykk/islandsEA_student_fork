import pika
from pika.adapters.blocking_connection import BlockingChannel


class CreateRabbitmqChannels:
    def __init__(
        self,
        number_of_islands: int,
        island: int,
        data_interval,
        last_step,
        max_evaluations,
        rabbitmq_delays,
        population_size,
        offspring_population_size,
        wyspWRun,
    ):
        self.wyspWRun = wyspWRun
        self.number_of_islands = number_of_islands
        self.island = island
        self.data_interval = data_interval
        self.last_step = last_step
        self.max_evaluations = max_evaluations
        self.rabbitmq_delays = rabbitmq_delays
        self.population_size = population_size
        self.offspring_population_size = offspring_population_size

    # TWORZENIE KOLEJEK GDY JEST WIĘCEJ WYSP
    def create_channels(self) -> BlockingChannel:
        channel = None
        if self.number_of_islands > 1:
            if self.island == 0:
                print(
                    "\n\nW G_I_A ",
                    self.number_of_islands,
                    " WYSP\ndata interval",
                    self.data_interval,
                    "\nlast step: ",
                    self.last_step,
                    ", max eval: ",
                    self.max_evaluations,
                    ", population size: ",
                    self.population_size,
                    ", offspring_population size: ",
                    self.offspring_population_size,
                    "\n\n",
                )

            if not (int(self.wyspWRun) == int(self.number_of_islands)):
                if self.island == 0:
                    print(
                        "\n\n !!!!!!!!!!!!!!\n NIEZGODNOSC LICZBY WYSP W run_alg i konfiguracji \n!!!!!!!!!!!!!!!!!"
                        + str(self.island)
                        + "\n\n"
                    )
                raise SystemExit

            connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
            channel = connection.channel()

            queue_name = f"island-{self.island}"

            if not self.isIslandDelayCorrect():
                if self.island == 0:
                    print(
                        "\n\n !!!!!!!!!!!!!!\n NIEWŁAŚCIWA ISLAND_DELAYS w algorith._configuration.json \n!!!!!!!!!!!!!!!!!"
                        + str(self.island)
                        + "\n\n"
                    )
                raise SystemExit

            # Configure queue for that island
            channel.queue_bind(exchange="amq.direct", queue=queue_name)

            # Configure delay queues for that island
            delay_channel = connection.channel()

            for i in range(0, self.number_of_islands):
                if i != self.island:
                    if self.rabbitmq_delays[str(self.island)][i] == -1:
                        continue
                    delay_channel.queue_bind(
                        exchange="amq.direct", queue=f"island-from-{self.island}-to-{i}"
                    )  # WIECEJ NIZ 1 WYSPA #1-end

        return channel

    # KONTROLA SPÓJNOŚCI PARAMETRÓW
    def isIslandDelayCorrect(self):
        message = ""
        isCorrect = True
        valuesInIslandDelay = []
        islandIn = []  # czy na daną wyspę jest kolejka wejściowa
        for i in range(self.number_of_islands):
            islandIn.append(False)
        for i in range(self.number_of_islands):
            islandOut = False  # czy z danej wyspy jest kolejka wyjsciowa
            for j in range(self.number_of_islands):
                if not i == j:
                    valuesInIslandDelay.append(self.rabbitmq_delays[str(i)][j])
                if not self.rabbitmq_delays[str(i)][j] == -1:
                    islandIn[j] = True
                    islandOut = True
            if not islandOut:
                message += "brak wyjscia z wyspy " + str(i) + "\n"
                isCorrect = False
        for i in range(self.number_of_islands):
            if not islandIn[i]:
                message += "brak wejscia na wyspe " + str(i) + "\n"
                isCorrect = False
        setOfValues = set(valuesInIslandDelay)

        # print("SoV",setOfValues)
        if setOfValues.__contains__(-1):  # ?????????????????
            setOfValues.remove(-1)
        if len(setOfValues) == 0:
            message += "ERROR - wszystkie kanały zamknięte <- tylko jedna wartość '-1' w IslandDelays poza przekątną\n"
            isCorrect = False
        if self.island == 0:
            print(message)
        return isCorrect
