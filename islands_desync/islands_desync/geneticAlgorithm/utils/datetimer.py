from datetime import datetime


class Datetimer:
    def __init__(self, kto, czy_kom) -> object:
        self.czy_kom = czy_kom
        if self.czy_kom:
            print("rusza dateTimer - wywolany przez " + str(kto))

    def __del__(self):
        if self.czy_kom:
            print("koniec datetimer")

    def czas(self):
        curDT = datetime.now()
        date_time = curDT.strftime("%y%m%d_g%H%M%S")
        return date_time

    def data(self):
        curDT = datetime.now()
        date_time = curDT.strftime("%y%m%d")
        return date_time

    def godz(self):
        curDT = datetime.now()
        date_time = curDT.strftime("g%H%M%S")
        return date_time

    def teraz(self):
        return datetime.now()

    def __str__(self):
        return "datetimer"


"""current day
day = curDT.strftime("%d")
print("day:", day)

current month
month = curDT.strftime("%m")
print("month:", month)

current year
year = curDT.strftime("%Y")
print("year:", year)

current time
time = curDT.strftime("%H:%M:%S")
print("time:", time)

current date and time
date_time = curDT.strftime("%m-%d-%Y g%H-%M-%S-%f")
print("date and time:", date_time)

aaa = "aaa,bbb,ccc"
print("-".join( aaa.split( ",")))
print("date and time:" + "=".join(date_time.split(",")))"""
