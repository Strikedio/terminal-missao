"""Leitura dos pendrives de missão.

Cada pendrive de missão tem um arquivo chamado pendrive.key com o nome dele
dentro (ex.: ALFA). Este módulo olha os pontos de montagem a cada chamada e
avisa quando um pendrive NOVO aparece. Quando o pendrive é removido e
colocado de novo, ele conta como uma nova inserção.
"""

import os
import string
import sys

ARQUIVO = "pendrive.key"


def _raizes():
    if sys.platform.startswith("win"):
        # começa em D: para não mexer em A:/B: (disquete) nem no disco do sistema
        return [f"{letra}:\\" for letra in string.ascii_uppercase[3:]]
    raizes = []
    for base in ("/media", "/run/media", "/mnt"):
        if not os.path.isdir(base):
            continue
        try:
            for n1 in os.listdir(base):
                p1 = os.path.join(base, n1)
                raizes.append(p1)
                if os.path.isdir(p1):
                    raizes += [os.path.join(p1, n2) for n2 in os.listdir(p1)]
        except OSError:
            pass
    return raizes


def ler_pendrives():
    """Devolve {ponto_de_montagem: NOME} dos pendrives com chave, agora."""
    achados = {}
    for raiz in _raizes():
        arquivo = os.path.join(raiz, ARQUIVO)
        try:
            if os.path.isfile(arquivo):
                with open(arquivo, encoding="utf-8") as f:
                    nome = f.read().strip().upper()
                if nome:
                    achados[raiz] = nome
        except OSError:
            pass
    return achados


class Monitor:
    def __init__(self):
        self.anteriores = ler_pendrives()  # o que já estava plugado não conta

    def atuais(self):
        return list(ler_pendrives().values())

    def varrer(self):
        """Uma leitura só: (nomes recém-inseridos, conjunto de nomes conectados agora)."""
        agora = ler_pendrives()
        novos = [nome for caminho, nome in agora.items() if caminho not in self.anteriores]
        self.anteriores = agora
        return novos, set(agora.values())

    def novos(self):
        """Nomes dos pendrives que acabaram de ser inseridos."""
        return self.varrer()[0]
