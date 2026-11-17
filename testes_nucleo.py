"""Testes automáticos do núcleo (sem tela e sem USB). Rodar:  python testes_nucleo.py"""

import random

from nucleo import NS, Config, Missao, cesar


class Rel:
    """Relógio falso em nanossegundos: avança só quando mandamos."""

    def __init__(self):
        self.t = 1_000

    def __call__(self):
        return self.t

    def passa(self, seg):
        self.t += int(seg * NS)


def nova(rel, **kw):
    m = Missao(Config(**kw), relogio=rel)
    m.iniciar()
    return m


def test_campanha_e_cronometro_para():
    r = Rel()
    m = nova(r, qtd_pendrives=3, codigo_hack="1234")
    assert m.cronometro() == (0, False)
    r.passa(5)
    assert m.cronometro() == (5 * NS, False)  # hacking: cronômetro sobe
    assert "negado" in m.tentar_codigo("1200")
    assert "CONCEDIDO" in m.tentar_codigo("1234") and m.estado == "DESARME"
    ns, reg = m.cronometro()
    assert reg and ns == 3 * 120 * NS  # desarme: regressivo
    r.passa(10)
    for n in m.ordem:
        m.inserir_pendrive(n)
    assert m.estado == "DESARMADO"
    parado = m.cronometro()
    r.passa(50)
    assert m.cronometro() == parado == (3 * 120 * NS - 10 * NS, True)  # PAROU ao desarmar


def test_desarme_detonacao():
    r = Rel()
    m = nova(r, modo="desarme", perfil="elite")
    m.inserir_pendrive(m.ordem[0])
    assert "reiniciada" in m.inserir_pendrive("ISCA") and m.progresso == []
    m.inserir_pendrive("ISCA")
    assert "DETONAÇÃO" in m.inserir_pendrive("ISCA") and m.estado == "DETONADO"
    r.passa(1000)
    assert m.cronometro()[0] == 3 * 75 * NS - 45 * NS  # congelado com as 3 penalidades
    m = nova(r, modo="desarme")
    r.passa(10_000)
    m.verificar_tempo()
    assert m.estado == "DETONADO" and m.cronometro() == (0, True)


def test_coleta_e_manual():
    r = Rel()
    m = nova(r, modo="coleta")
    assert "CORROMPIDO" in m.inserir_pendrive("xx")
    m.inserir_pendrive("bravo")
    assert "já" in m.inserir_pendrive("BRAVO")
    m.avancar_etapa()
    m.avancar_etapa()
    assert m.estado == "CONCLUIDO" and sorted(m.progresso) == ["ALFA", "BRAVO", "CHARLIE"]


def test_decifrar():
    r = Rel()
    assert cesar("ZEBRA", 3) == "CHEUD"
    m = nova(r, modo="decifrar", codigo_hack="escudo", chave=5)
    assert m.cifrado == cesar("ESCUDO", 5) and m.chave == 5
    assert "INCORRETA" in m.tentar_codigo("falcao")
    assert "DECIFRADA" in m.tentar_codigo("escudo") and m.estado == "CONCLUIDO"
    m = nova(r, modo="decifrar")  # sorteia palavra e chave
    assert m.chave in range(1, 26) and m.cfg.codigo_hack.isalpha()
    m.avancar_etapa()
    assert m.estado == "CONCLUIDO"
    try:
        Config(modo="decifrar", codigo_hack="AÇÃO")
        assert False
    except ValueError:
        pass


def test_download():
    r = Rel()
    m = nova(r, modo="download", perfil="normal", qtd_pendrives=3)  # 35 s por pendrive
    m.definir_presentes({"ALFA"})
    r.passa(20)
    m.verificar_tempo()
    m.definir_presentes(set())
    r.passa(1)
    m.verificar_tempo()  # removeu: pausa (normal)
    assert any("pausada" in t for t, _ in m.pop_eventos()) and m.acum["ALFA"] == 20 * NS
    m.definir_presentes({"ALFA"})
    r.passa(10)
    m.verificar_tempo()
    r.passa(10)
    m.verificar_tempo()
    assert m.progresso == ["ALFA"]  # 20 + 15 s
    m.definir_presentes({"BRAVO", "CHARLIE"})
    r.passa(36)
    m.verificar_tempo()
    assert m.estado == "CONCLUIDO" and m.msg_final == "TRANSFERÊNCIA COMPLETA"
    ns = m.cronometro()
    r.passa(100)
    assert m.cronometro() == ns  # cronômetro parado
    # elite reinicia ao remover; isca estoura os erros; tempo esgotado
    m = nova(r, modo="download", perfil="elite")
    m.definir_presentes({"ALFA"})
    r.passa(30)
    m.verificar_tempo()
    m.definir_presentes(set())
    r.passa(1)
    m.verificar_tempo()
    assert m.acum["ALFA"] == 0 and any("REINICIADA" in t for t, _ in m.pop_eventos())
    m.inserir_pendrive("ISCA")
    assert "ALARME" in m.inserir_pendrive("ISCA") + m.inserir_pendrive("ISCA")
    assert m.estado == "FALHOU"
    m = nova(r, modo="download")
    r.passa(10_000)
    m.verificar_tempo()
    assert m.estado == "FALHOU" and m.msg_final == "TEMPO ESGOTADO"
    m = nova(r, modo="download", tempo_s=60, qtd_pendrives=3)  # 60 s no total = 20 s por pendrive
    m.avancar_etapa()
    assert m.progresso == ["ALFA"]


def test_defesa():
    random.seed(1)
    r = Rel()
    m = nova(r, modo="defesa", perfil="normal")
    m.verificar_tempo()
    assert m.ataque is None
    r.passa(30)
    m.verificar_tempo()
    assert m.ataque is not None and any("INTRUSÃO" in t for t, _ in m.pop_eventos())
    assert "INCORRETO" in m.tentar_codigo("XXXX") and m.ataque
    assert "BLOQUEADA" in m.tentar_codigo(m.ataque["codigo"]) and m.ataque is None
    for _ in range(3):  # ignora 3 intrusões: servidor cai
        r.passa(40)
        m.verificar_tempo()
        r.passa(11)
        m.verificar_tempo()
    assert m.estado == "FALHOU" and m.msg_final == "SERVIDOR COMPROMETIDO"
    ns = m.cronometro()
    r.passa(99)
    assert m.cronometro() == ns
    m = nova(r, modo="defesa", tempo_s=60)  # sobrevive até o fim
    r.passa(61)
    m.verificar_tempo()
    assert m.estado == "CONCLUIDO" and m.msg_final == "DEFESA BEM-SUCEDIDA"
    m = nova(r, modo="defesa")
    r.passa(30)
    m.verificar_tempo()
    assert "BLOQUEADA" in m.avancar_etapa()  # organizador bloqueia manualmente


def test_controle():
    r = Rel()
    m = nova(r, modo="controle", perfil="treino")  # meta 60 s
    m.definir_presentes({"VERMELHO"})
    r.passa(30)
    m.verificar_tempo()
    m.definir_presentes({"VERMELHO", "AZUL"})
    r.passa(100)
    m.verificar_tempo()  # disputa: ninguém pontua
    assert m.acum_eq["VERMELHO"] == 30 * NS and m.acum_eq["AZUL"] == 0
    m.definir_presentes({"AZUL"})
    r.passa(59)
    m.verificar_tempo()
    assert m.estado == "CONTROLE"  # 30 + 59 s < 60? não: AZUL tem 59 s
    r.passa(2)
    m.verificar_tempo()
    assert m.estado == "CONCLUIDO" and m.vencedor == "AZUL" and "AZUL" in m.msg_final
    assert "INVÁLIDA" in nova(r, modo="controle").inserir_pendrive("ISCA")


def test_validacao():
    for kw in (
        {"qtd_pendrives": 2},
        {"qtd_pendrives": 9},
        {"modo": "x"},
        {"perfil": "x"},
        {"chave": 26},
        {"tempo_s": -1},
    ):
        try:
            Config(**kw)
            assert False, kw
        except ValueError:
            pass
    for modo in (
        "campanha",
        "hacking",
        "coleta",
        "desarme",
        "decifrar",
        "download",
        "defesa",
        "controle",
    ):
        m = nova(Rel(), modo=modo)
        assert m.painel()["info"] is not None and m.resumo_admin()


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print("ok  ", t.__name__)
    print(f"\n{len(testes)} grupos de teste passaram.")
