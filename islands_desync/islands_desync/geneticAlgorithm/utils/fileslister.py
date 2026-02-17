import fnmatch
import os


class FilesLister:
    def __init__(self, kto, czy_kom):
        self.czy_kom = czy_kom
        if self.czy_kom:
            print("rusza fileLister - wywolany przez " + str(kto))

    def listFilesExtensionLike(self, katalog, extension):
        lista = []
        lista_elementow = os.listdir(katalog)
        for element in lista_elementow:
            pelna_sciezka = os.path.join(katalog, element)
            if not os.path.isdir(pelna_sciezka):
                if pelna_sciezka.endswith(extension):
                    lista.append(pelna_sciezka)
        return lista

    def countFilesExtensionLike(self, katalog, extension):
        lista = []
        lista_elementow = os.listdir(katalog)
        for element in lista_elementow:
            pelna_sciezka = os.path.join(katalog, element)
            if not os.path.isdir(pelna_sciezka):
                if pelna_sciezka.endswith(extension):
                    lista.append(pelna_sciezka)
        return lista.__len__()

    def __str__(self):
        return "fileslister"

    def __del__(self):
        if self.czy_kom:
            print("koniec filelister")

    def list_paths(self):  # no usage found
        folder = "."
        pattern = "*"
        case_sensitive = False
        subfolders = False
        match = fnmatch.fnmatchcase if case_sensitive else fnmatch.fnmatch
        walked = os.walk(folder) if subfolders else [next(os.walk(folder))]
        return [
            os.path.join(root, f)
            for root, dirnames, filenames in walked
            for f in filenames
            if match(f, pattern)
        ]

    def listOfSubfolders(
        self, katalog
    ):  # , ext2like, ext3like): # przy przeszukiwaniu podkatalogów
        lista_elementow = os.listdir(katalog)
        properSubkat = []
        for element in lista_elementow:
            if os.path.isdir(katalog + "/" + element):
                properSubkat.append(element)
        return properSubkat

    def listOfSubfoldersEndingWith(
        self, katalog, ext1Like
    ):  # , ext2like, ext3like): # przy przeszukiwaniu podkatalogów
        lista_elementow = os.listdir(katalog)
        properSubkat = []
        for element in lista_elementow:
            if element.endswith(ext1Like):
                properSubkat.append(element)
        return properSubkat

    def listOfFilesNameConteining(
        self, katalog, ext2like
    ):  # przy przeszukiwaniu podkatalogów
        listaOut = []
        lista_elementow = os.listdir(katalog)
        for element in lista_elementow:
            if element.__contains__(ext2like):
                # print(katalog+"/"+element)
                listaOut.append(element)
        return listaOut

    def listInsideSubfolders(
        self, katalog, properSubkat, ext2like, ext3like
    ):  # przy przeszukiwaniu podkatalogów testSB6
        listaOut = []
        for i in range(len(properSubkat)):
            listTmp = []
            listTmp.append(
                FilesLister.listFilesExtensionLike(
                    0, katalog + "/" + properSubkat[i], ext3like
                )
            )
            listaOut.append(
                [elem for elem in listTmp[0] if elem.__contains__(ext2like)]
            )
        return listaOut

        """listaOut=[]
        for element in lista_elementow:
            pelna_sciezka = os.path.join(katalog, element)
            if os.path.isdir(pelna_sciezka):
                FilesLister.listuj(self, pelna_sciezka,extLike)
            else:
                #print(extLike)
                #print(pelna_sciezka)
                if pelna_sciezka.endswith(extLike):
                    listaOut.append(pelna_sciezka)
                    print(pelna_sciezka,"<--------------",len(listaOut))
        print(listaOut,"    OUT")
        return listaOut"""

    def makelist(self, katalog):  # no usage found
        lista = []
        lista_elementow = os.listdir(katalog)
        for element in lista_elementow:
            pelna_sciezka = os.path.join(katalog, element)
            if os.path.isdir(pelna_sciezka):
                print(" ")
                # Lister.listuj(pelna_sciezka)
            else:
                # print(pelna_sciezka)
                lista.append(pelna_sciezka)
        return lista

    def z_pliku(self):  # no usage found
        print(os.listdir("./generator"))
        thisdir = os.getcwd()
        # r=root, d=directories, f = files
        for r, d, f in os.walk(thisdir):
            for file in f:
                if file.endswith(".docx"):
                    print(os.path.join(r, file))
