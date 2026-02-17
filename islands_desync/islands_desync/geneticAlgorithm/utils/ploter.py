import matplotlib.pyplot as plt


class Ploter:
    def __init__(self, czy_kom):
        self.czy_kom = czy_kom
        # self.kolorki(['black', 'red', 'darkcyan', 'yellow', 'green', 'blue', 'cyan', 'tab:orange', 'tab:olive', 'tab:pink','tab:gray', 'tab:brown'])
        if self.czy_kom:
            print("rusza ploter ")

    def rysLine_z_tab100_dopliku(
        self, x, y, fileP, kt_wyspa, data_interval, title
    ):  # tablice z X-ami i Y-ami
        kolorki = [
            "black",
            "red",
            "darkcyan",
            "yellow",
            "green",
            "blue",
            "cyan",
            "tab:orange",
            "tab:olive",
            "tab:pink",
            "tab:gray",
            "tab:brown",
        ]
        plt.plot(x, y, color=kolorki[kt_wyspa + 1])
        # plt.yscale('log')
        plt.title(title)
        plt.savefig(fileP + ".png")
        plt.close()

    def rysLine_z_tab_dopliku(self, x, y, fileP, kt_wyspa, title):
        kolorki = [
            "black",
            "red",
            "darkcyan",
            "yellow",
            "green",
            "blue",
            "cyan",
            "tab:orange",
            "tab:olive",
            "tab:pink",
            "tab:gray",
            "tab:brown",
        ]
        # plt.plot(x, y)           #todo: po co te kropki?????????????????????
        plt.plot(
            x, y, color=kolorki[kt_wyspa + 1]
        )  # , 'bs')  # t, t, 'r--', t, t ** 2, 'bs', t, t ** 3, 'g^') # todo: co to jest 'bs'
        plt.title(title)
        plt.savefig(fileP + ".png")
        plt.close()

    def rysLine_z_Ntab_dopliku(self, fileP, tabele, title, seria):
        # print("==================",fileP, tabele,title,seria)
        kolorki = [
            "black",
            "red",
            "darkcyan",
            "yellow",
            "green",
            "blue",
            "cyan",
            "tab:orange",
            "tab:olive",
            "tab:pink",
            "tab:gray",
            "tab:brown",
        ]
        lk = len(kolorki)
        markers = [".", "o", "x", "."]
        linestyle = ["-", "--", "-.", ":"]
        lm = len(markers)
        legenda = []
        # print("----------",len(tabele[0]))
        nummarker = -1
        if len(tabele[0]) == 3:
            for i in range(len(tabele)):
                if i % lk == 0:
                    nummarker += 1
                legenda.append(tabele[i][2])
                plt.plot(
                    tabele[i][0],
                    tabele[i][1],
                    color=kolorki[(i + 1) % lk],
                    linestyle=linestyle[nummarker],
                    linewidth=1,
                )

        else:
            if seria:
                for i in range(len(tabele)):
                    # print(self.kolory[i+1])
                    plt.plot(tabele[i][0], tabele[i][1], color=kolorki[i])

                    if i == 0:
                        legenda.append("average ")
                    else:
                        legenda.append("experiment " + str(i))
            else:
                for i in range(len(tabele)):
                    # print(self.kolory[i+1])
                    plt.plot(tabele[i][0], tabele[i][1], color=kolorki[i + 1])
                    legenda.append("island " + str(i))

        # print(legenda)

        plt.yscale("log")
        plt.legend(legenda, loc="center right", fontsize=5)  #  loc ="lower right"
        plt.title(title)
        plt.savefig(fileP + ".png")
        plt.close()

    def rysDot_z_Ntab_dopliku(self, fileP, tabele, title):
        # print("N-2D",fileP)
        kolorki = [
            "black",
            "red",
            "darkcyan",
            "yellow",
            "green",
            "blue",
            "cyan",
            "tab:orange",
            "tab:olive",
            "tab:pink",
            "tab:gray",
            "tab:brown",
        ]
        plt.scatter(tabele[0][0], tabele[0][1], marker="*", color=kolorki[0])
        for i in range(len(tabele) - 1):
            plt.scatter(
                tabele[i + 1][0], tabele[i + 1][1], color=kolorki[i + 1]
            )  # ,figsize=(25, 5))
        plt.title(title)
        plt.savefig(fileP + " W 0-" + str(len(tabele) - 2) + ".png")
        plt.close()

        for i in range(len(tabele) - 1):
            plt.scatter(tabele[i + 1][0], tabele[i + 1][1], color=kolorki[i + 1])
        plt.title(title)
        plt.savefig(fileP + " W 0-" + str(len(tabele) - 2) + "--.png")
        plt.close()

    def rysDot_z_tab_dopliku(self, xa, ya, x, y, fileP, numWyspy, title):
        # print("1-2D", fileP)
        kolorki = [
            "black",
            "red",
            "darkcyan",
            "yellow",
            "green",
            "blue",
            "cyan",
            "tab:orange",
            "tab:olive",
            "tab:pink",
            "tab:gray",
            "tab:brown",
        ]
        plt.scatter(xa, ya, marker="*", color="black")  # edgecolor ="blue",
        plt.scatter(x, y, color=kolorki[numWyspy + 1])
        plt.title(title)
        plt.savefig(fileP + ".png")
        plt.close()

        plt.scatter(x, y, color=kolorki[numWyspy + 1])
        plt.title(title)
        plt.savefig(fileP + "--.png")
        plt.close()

    def rysDot3d_z_tab_dopliku(self, xa, ya, za, x, y, z, fileP, numWyspy, title):
        # print("3D-1", fileP)
        kolorki = [
            "black",
            "red",
            "darkcyan",
            "yellow",
            "green",
            "blue",
            "cyan",
            "tab:orange",
            "tab:olive",
            "tab:pink",
            "tab:gray",
            "tab:brown",
        ]

        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")

        ax.scatter(xa, ya, za, marker="*", color=kolorki[0])  # , edgecolor ="blue"
        ax.scatter(x, y, z, marker="o", c=kolorki[numWyspy + 1])
        plt.title(title)
        # plt.xlabel("os X")
        # plt.ylabel("os Y")
        plt.savefig(fileP + ".png")
        plt.close()

        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        ax.scatter(x, y, z, marker="o", c=kolorki[numWyspy + 1])
        plt.title(title)
        # plt.xlabel("os X")
        # plt.ylabel("os Y")
        plt.savefig(fileP + "--.png")
        plt.close()

    def rysDot3d_z_Ntab_dopliku(self, tabele, fileP, title):
        # print("N-3D", fileP)
        kolorki = [
            "black",
            "red",
            "darkcyan",
            "yellow",
            "green",
            "blue",
            "cyan",
            "tab:orange",
            "tab:olive",
            "tab:pink",
            "tab:gray",
            "tab:brown",
        ]

        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")

        ax.scatter(
            tabele[0][0], tabele[0][1], tabele[0][2], marker="*", color=kolorki[0]
        )  # , edgecolor ="blue"

        # print("LT", len(tabele))
        for i in range(len(tabele) - 1):
            ax.scatter(
                tabele[i + 1][0],
                tabele[i + 1][1],
                tabele[i + 1][2],
                marker="o",
                c=kolorki[i + 1],
            )

        plt.title(title)
        # plt.xlabel("os X")
        # plt.ylabel("os Y")

        plt.savefig(fileP + " W 0-" + str(len(tabele) - 2) + ".png")
        plt.close()

        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        for i in range(len(tabele) - 1):
            ax.scatter(
                tabele[i + 1][0],
                tabele[i + 1][1],
                tabele[i + 1][2],
                marker="o",
                c=kolorki[i + 1],
            )

        plt.title(title)
        # plt.xlabel("os X")
        # plt.ylabel("os Y")

        plt.savefig(fileP + " W 0-" + str(len(tabele) - 2) + "--.png")
        plt.close()

    def __str__(self):
        return "to ja ploter"

    def __del__(self):
        if self.czy_kom:
            print("koniec ploter")
