"""Testes do gravador de pendrives (sem hardware). Rodar:  python testes_gravador.py"""

import os
import tempfile

import gravador
from leitor_usb import ARQUIVO


class PendriveFalso:
    """Pasta temporária que faz o papel de um pendrive montado."""

    def __init__(self):
        self.pasta = tempfile.mkdtemp(prefix="pendrive_falso_")
        self.original = gravador._raizes_linux
        gravador._raizes_linux = lambda: [self.pasta]
        self.plataforma = gravador.sys.platform
        gravador.sys.platform = "linux"

    def restaurar(self):
        gravador._raizes_linux = self.original
        gravador.sys.platform = self.plataforma


def test_nomes():
    assert gravador.normalizar_nome("  alfa ") == "ALFA"
    assert gravador.normalizar_nome("hotel_2") == "HOTEL_2"
    for ruim in ("", "   ", "A B", "AÇÃO", "X" * 21, "../ALFA", None):
        try:
            gravador.normalizar_nome(ruim)
            raise AssertionError(f"deveria recusar {ruim!r}")
        except ValueError:
            pass


def test_sugestoes_e_proximo():
    nomes = gravador.nomes_sugeridos()
    assert nomes[0] == "ALFA" and "VERMELHO" in nomes and nomes[-1] == "ISCA"
    assert gravador.proximo_nome("alfa") == "BRAVO"
    assert gravador.proximo_nome("ISCA") == "ALFA"  # volta ao começo
    assert gravador.proximo_nome("QUALQUER") == "ALFA"  # nome fora da lista


def test_listar_e_gravar():
    falso = PendriveFalso()
    try:
        itens = gravador.listar_pendrives()
        assert [i["caminho"] for i in itens] == [falso.pasta] and itens[0]["nome"] == ""
        assert "sem chave" in gravador.descrever(itens[0])
        ok, msg = gravador.gravar(falso.pasta, "bravo")
        assert ok and "BRAVO" in msg
        assert open(os.path.join(falso.pasta, ARQUIVO), encoding="utf-8").read() == "BRAVO"
        assert gravador.ler_nome(falso.pasta) == "BRAVO"
        assert "chave: BRAVO" in gravador.descrever(gravador.listar_pendrives()[0])
        ok, _ = gravador.gravar(falso.pasta, "charlie")  # sobrescreve
        assert ok and gravador.ler_nome(falso.pasta) == "CHARLIE"
    finally:
        falso.restaurar()


def test_gravar_recusas():
    falso = PendriveFalso()
    try:
        ok, msg = gravador.gravar(falso.pasta, "nome inválido!")
        assert not ok and "inválido" in msg
        outra = tempfile.mkdtemp(prefix="nao_removivel_")
        ok, msg = gravador.gravar(outra, "ALFA")  # não é pendrive detectado
        assert not ok and "removível" in msg
        assert not os.path.exists(os.path.join(outra, ARQUIVO))
        ok, _ = gravador.gravar(outra, "ALFA", permitir_qualquer=True)  # com confirmação
        assert ok
        ok, msg = gravador.gravar(os.path.join(outra, "nao_existe"), "ALFA", permitir_qualquer=True)
        assert not ok and "Erro" in msg
    finally:
        falso.restaurar()


def test_ler_nome_sem_arquivo():
    assert gravador.ler_nome(tempfile.mkdtemp()) == ""
    assert gravador.ler_nome("/caminho/que/nao/existe") == ""


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for teste in testes:
        teste()
        print("ok  ", teste.__name__)
    print(f"\n{len(testes)} grupos de teste passaram.")
