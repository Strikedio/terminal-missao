"""Teste no console (sem tela e sem USB): jogue qualquer modo digitando no teclado.

Rodar:  python teste_console.py
Digite o código/palavra quando a etapa pedir código, ou o nome do pendrive.
Nos modos de "manter conectado" (download, controle), digitar o nome conecta o pendrive
e digitar de novo desconecta. Comandos: ok = só passar o tempo | + = avançar etapa | sair
"""

from nucleo import FINAIS, MODOS, NS, PERFIS, Config, Missao

COM_CODIGO = ("HACKING", "DECIFRAR", "DEFESA")


def perguntar(texto, opcoes, padrao):
    while True:
        r = input(f"{texto} {list(opcoes)} [{padrao}]: ").strip().lower() or padrao
        if r in opcoes:
            return r
        print("Opção inválida.")


def fmt(ns):
    seg, resto = divmod(int(ns), NS)
    return f"{seg // 60:02d}:{seg % 60:02d}.{resto:09d}"


def main():
    print("=== TERMINAL DE MISSÃO (teste no console) ===")
    modo = perguntar("Modo", MODOS, "campanha")
    perfil = perguntar("Perfil", PERFIS, "normal")
    qtd = int(input("Pendrives (3 a 8) [3]: ") or 3)
    missao = Missao(Config(modo=modo, perfil=perfil, qtd_pendrives=qtd))
    if input("Mostrar a solução (só para testes)? [s/N]: ").lower() == "s":
        print("  [DEBUG]", missao.resumo_admin().replace("\n", " | "))
    missao.iniciar()
    conectados = set()

    def eventos():
        for texto, _som in missao.pop_eventos():
            print("  *", texto)

    while True:
        missao.definir_presentes(conectados)
        missao.verificar_tempo()
        eventos()
        ns, regressivo = missao.cronometro()
        p = missao.painel()
        print(f"\n[{missao.estado}] {'restante' if regressivo else 'decorrido'}: {fmt(ns)}")
        if p["ordem"]:
            print(" ", p["ordem"])
        if p["info"]:
            print(" ", p["info"])
        if missao.estado in FINAIS:
            break
        entrada = input("> ").strip()
        if entrada.lower() == "sair":
            return
        if entrada.lower() == "ok" or not entrada:
            continue
        if entrada == "+":
            print(" ", missao.avancar_etapa())
        elif missao.fase in COM_CODIGO:
            print(" ", missao.tentar_codigo(entrada))
        elif modo in ("download", "controle"):
            nome = entrada.upper()
            if nome in conectados:
                conectados.discard(nome)
                print(f"  {nome} desconectado")
            else:
                conectados.add(nome)
                print(" ", missao.inserir_pendrive(nome))
        else:
            print(" ", missao.inserir_pendrive(entrada))
        eventos()

    print(
        f"\n=== FIM DA MISSÃO: {missao.msg_final or missao.estado} | cronômetro parado em {fmt(ns)} ==="
    )


if __name__ == "__main__":
    main()
