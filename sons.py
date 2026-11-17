"""Efeitos sonoros gerados por código (nenhum arquivo de áudio é necessário).

Windows: usa winsound. Linux: usa paplay ou aplay (pacote alsa-utils).
"""

import math
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import wave

TAXA = 22050
# nome: [(frequência Hz, duração s, volume 0-1)]  | frequência 0 = ruído (explosão)
SONS = {
    "beep": [(880, 0.08, 0.5)],
    "ok": [(660, 0.10, 0.5), (990, 0.15, 0.5)],
    "erro": [(180, 0.45, 0.7)],
    "alarme": [(800, 0.3, 0.6), (600, 0.3, 0.6)] * 3,
    "vitoria": [(523, 0.15, 0.5), (659, 0.15, 0.5), (784, 0.15, 0.5), (1047, 0.4, 0.5)],
    "explosao": [(0, 1.8, 0.9)],
}
_caminhos = {}


def _gerar(caminho, trechos):
    dados = bytearray()
    for freq, dur, vol in trechos:
        n = int(TAXA * dur)
        for i in range(n):
            if freq == 0:
                v = random.uniform(-1, 1) * (1 - i / n) ** 2
            else:
                fade = min(1.0, i / 150, (n - i) / 150)
                v = math.sin(2 * math.pi * freq * i / TAXA) * fade
            dados += struct.pack("<h", int(32767 * vol * v))
    with wave.open(caminho, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(bytes(dados))


def preparar():
    pasta = tempfile.mkdtemp(prefix="airsoft_sons_")
    for nome, trechos in SONS.items():
        caminho = os.path.join(pasta, nome + ".wav")
        _gerar(caminho, trechos)
        _caminhos[nome] = caminho


def tocar(nome):
    caminho = _caminhos.get(nome)
    if not caminho:
        return
    try:
        if sys.platform.startswith("win"):
            import winsound

            winsound.PlaySound(caminho, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        for cmd in (["paplay"], ["aplay", "-q"]):
            if shutil.which(cmd[0]):
                threading.Thread(
                    target=subprocess.run,
                    args=(cmd + [caminho],),
                    kwargs={"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL},
                    daemon=True,
                ).start()
                return
    except Exception:
        pass  # som nunca pode derrubar o jogo
