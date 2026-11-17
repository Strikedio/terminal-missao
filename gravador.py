"""Gravação dos pendrives de missão.

Cada pendrive de missão guarda um arquivo ``pendrive.key`` com o nome dele
(ALFA, BRAVO...). Este módulo localiza os pendrives removíveis conectados e
grava (e confere) esse arquivo. É usado pelo painel do organizador (F12) e
pelo gravar_pendrive.py.
"""

import ctypes
import os
import re
import string
import sys

from leitor_usb import ARQUIVO
from nucleo import EQUIPES, NOMES_PENDRIVES

NOME_ISCA = "ISCA"
PADRAO_NOME = re.compile(r"^[A-Z0-9_-]{1,20}$")
DRIVE_REMOVIVEL = 2  # valor de GetDriveTypeW para pendrives no Windows


def nomes_sugeridos():
    """Nomes que o jogo reconhece, mais ISCA (pendrive falso)."""
    return list(NOMES_PENDRIVES) + list(EQUIPES) + [NOME_ISCA]


def proximo_nome(nome):
    """Próximo nome da lista de sugestões (para gravar vários pendrives em sequência)."""
    lista = nomes_sugeridos()
    try:
        return lista[(lista.index(nome.strip().upper()) + 1) % len(lista)]
    except ValueError:
        return lista[0]


def normalizar_nome(texto):
    """Maiúsculas, sem espaços nas pontas; levanta ValueError se o nome for inválido."""
    nome = (texto or "").strip().upper()
    if not PADRAO_NOME.match(nome):
        raise ValueError("Nome inválido: use de 1 a 20 letras, números, - ou _ (sem acento).")
    return nome


def _raizes_windows():
    kernel32 = ctypes.windll.kernel32
    mascara = kernel32.GetLogicalDrives()
    raizes = []
    for i, letra in enumerate(string.ascii_uppercase):
        if mascara & (1 << i):
            raiz = f"{letra}:\\"
            if kernel32.GetDriveTypeW(raiz) == DRIVE_REMOVIVEL:
                raizes.append(raiz)
    return raizes


def _raizes_linux():
    """Pontos de montagem de mídia removível (udisks monta em /media/<usuario>/<rótulo>)."""
    raizes = []
    try:
        with open("/proc/mounts", encoding="utf-8") as arq:
            for linha in arq:
                partes = linha.split()
                if len(partes) < 2:
                    continue
                ponto = partes[1].replace("\\040", " ")
                if ponto.startswith(("/media/", "/run/media/")):
                    raizes.append(ponto)
    except OSError:
        pass
    return raizes


def ler_nome(raiz):
    """Nome gravado em pendrive.key dentro de `raiz` ('' se não houver)."""
    try:
        with open(os.path.join(raiz, ARQUIVO), encoding="utf-8") as arq:
            return arq.read().strip().upper()
    except OSError:
        return ""


def listar_pendrives():
    """Pendrives removíveis conectados: [{'caminho', 'rotulo', 'nome'}, ...]."""
    raizes = _raizes_windows() if sys.platform.startswith("win") else _raizes_linux()
    achados = []
    for raiz in raizes:
        if os.path.isdir(raiz):
            rotulo = os.path.basename(raiz.rstrip("/\\")) or raiz
            achados.append({"caminho": raiz, "rotulo": rotulo, "nome": ler_nome(raiz)})
    return achados


def descrever(item):
    """Texto de uma linha para mostrar o pendrive ao organizador."""
    chave = f"chave: {item['nome']}" if item["nome"] else "sem chave"
    return f"{item['caminho']}  [{item['rotulo']}]  {chave}"


def gravar(caminho, nome, permitir_qualquer=False):
    """Grava pendrive.key em `caminho` e confere. Devolve (ok, mensagem); nunca levanta exceção.

    Por segurança só grava em pendrives removíveis detectados, a menos que
    `permitir_qualquer` seja verdadeiro (usado pelo gravar_pendrive.py, com confirmação).
    """
    try:
        nome = normalizar_nome(nome)
        if not permitir_qualquer and caminho not in {p["caminho"] for p in listar_pendrives()}:
            return False, "Esse caminho não é um pendrive removível conectado."
        with open(os.path.join(caminho, ARQUIVO), "w", encoding="utf-8") as arq:
            arq.write(nome)
            arq.flush()
            os.fsync(arq.fileno())
        if hasattr(os, "sync"):
            os.sync()
        if ler_nome(caminho) != nome:
            return False, "Falha ao conferir a gravação. Tente de novo."
        return True, f"{nome} gravado em {caminho}"
    except ValueError as erro:
        return False, str(erro)
    except OSError as erro:
        return False, f"Erro ao gravar: {erro}"
