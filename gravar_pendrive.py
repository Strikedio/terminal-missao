"""Prepara os pendrives da missão pelo terminal (alternativa ao painel F12).

Rodar:  python gravar_pendrive.py

Lista os pendrives removíveis conectados e grava neles o arquivo pendrive.key
com o nome escolhido (ALFA, BRAVO..., VERMELHO, AZUL ou ISCA para pendrive falso).
"""

import gravador


def escolher_pendrive():
    """Pede ao usuário para escolher um pendrive. Devolve (caminho, permitir_qualquer) ou None."""
    itens = gravador.listar_pendrives()
    if itens:
        print("\nPendrives detectados:")
        for numero, item in enumerate(itens, start=1):
            print(f"  {numero}) {gravador.descrever(item)}")
    else:
        print("\nNenhum pendrive removível detectado.")
    resposta = (
        input("Número do pendrive (ou caminho completo; Enter para sair): ").strip().strip('"')
    )
    if not resposta:
        return None
    if resposta.isdigit() and 1 <= int(resposta) <= len(itens):
        return itens[int(resposta) - 1]["caminho"], False
    detectados = {item["caminho"] for item in itens}
    if resposta not in detectados:
        aviso = "Esse caminho NÃO é um pendrive removível detectado. Gravar mesmo assim? [s/N]: "
        if input(aviso).strip().lower() != "s":
            return escolher_pendrive()
        return resposta, True
    return resposta, False


def main():
    print("=== GRAVADOR DE PENDRIVES DE MISSÃO ===")
    print("Nomes da missão:", ", ".join(gravador.nomes_sugeridos()))
    sugestao = gravador.nomes_sugeridos()[0]
    while True:
        escolha = escolher_pendrive()
        if escolha is None:
            break
        caminho, permitir = escolha
        nome = input(f"Nome deste pendrive [{sugestao}]: ").strip() or sugestao
        ok, mensagem = gravador.gravar(caminho, nome, permitir_qualquer=permitir)
        print(f"  {'OK' if ok else 'FALHA'}: {mensagem}")
        if ok:
            sugestao = gravador.proximo_nome(nome)
    print("Pronto. Dica: etiquete cada pendrive com o nome gravado.")


if __name__ == "__main__":
    main()
