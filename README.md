# Terminal de Missão (Airsoft)

Um notebook que vira **item de missão** em jogos de airsoft. Os operadores interagem só com **teclado, tela e pendrives**
espalhados pelo campo. O organizador configura tudo por um painel escondido (F12).

- Python 3 + tkinter, sem dependências externas.
- Roda em Windows (para testar) e em Linux (Debian 13 em modo quiosque, sem desktop).
- Cronômetro em **nanossegundos** que para quando a missão termina.

## Modos de missão

| Modo | Resumo |
|------|--------|
| `campanha` | Encadeia hacking → coleta → desarme numa missão só |
| `hacking` | Invadir o sistema digitando o código correto, com número limitado de tentativas |
| `coleta` | Inserir os pendrives na ordem indicada pelo terminal |
| `desarme` | Inserir a sequência certa antes do tempo acabar; erro custa 15 s (ou detona) |
| `decifrar` | Decifrar uma mensagem em cifra de César usando a chave encontrada nos pendrives |
| `download` | Manter o pendrive conectado até o download terminar; desconectar reinicia o progresso |
| `defesa` | Resistir até o fim do tempo digitando o código de bloqueio de cada intrusão antes do prazo; intrusões concluídas reduzem a integridade |
| `controle` | Cada equipe (VERMELHO e AZUL) tem um pendrive; quem o mantém conectado sozinho pontua. Com os dois conectados o ponto fica em disputa. Vence quem atingir a meta de tempo |

Dificuldade: **treino**, **normal** ou **elite**. Quantidade de pendrives: de 3 a 8 (padrão 3), definida pelo organizador.
Funciona para 2 jogadores ou para 10 ou mais.

## Teclas do organizador (não aparecem na tela dos operadores)

| Tecla | Função |
|-------|--------|
| **F12** (ou Ctrl+Shift+A) | Painel do organizador (pede senha) |
| **F5** | Mostra/esconde a caixa para **simular um pendrive** digitando o nome (teste ou falha na porta USB) |
| **F6** | **Avança a etapa** manualmente |

A senha inicial é **`admin`**. **Troque-a no painel F12** antes de jogar. F5 e F6 também pedem a senha
(depois de digitá-la valem por 60 s).

### Painel F12

Escolha de modo, dificuldade, quantidade de pendrives, código de hack, chave e tempo; nova senha; e os botões:

- **GRAVAR PENDRIVES**: tela para preparar os pendrives (veja abaixo);
- **SIMULAR PENDRIVE (F5)** e **AVANÇAR ETAPA (F6)**;
- **ABORTAR MISSÃO** e **VOLTAR**;
- **DESLIGAR NOTEBOOK** (só no Linux; pede 2 cliques em até 5 s);
- **SAIR DO PROGRAMA**.

## Pendrives

Cada pendrive de missão tem na raiz um arquivo **`pendrive.key`** com o nome dele: `ALFA`, `BRAVO`, `CHARLIE`, `DELTA`,
`ECO`, `FOXTROT`, `GOLF`, `HOTEL` (ou `VERMELHO`, `AZUL` no modo controle, ou `ISCA` para um pendrive falso).
Pendrives já conectados quando o programa abre **não contam** como inserção.

### Gravar pendrives

1. **Pelo painel:** F12 → senha → **GRAVAR PENDRIVES** → conecte o pendrive → escolha o nome → **GRAVAR**.
   O nome seguinte (BRAVO, CHARLIE...) é sugerido automaticamente. A gravação é conferida por releitura.
2. **Pelo terminal:** `python gravar_pendrive.py`.

Etiquete fisicamente cada pendrive com o nome gravado. O programa só grava em pendrives **removíveis** detectados.

## Uso

### Windows (testes)

```
python terminal.py --janela      # em janela
python terminal.py               # tela cheia
python terminal.py --teste       # já abre com a caixa de pendrive simulado
```

Requer Python 3.9+ com tkinter (incluído no instalador oficial).

### Linux

```
sudo apt install python3 python3-tk
python3 terminal.py --janela
```

### Notebook dedicado (Debian sem interface gráfica)

O notebook liga e abre direto o terminal, sem desktop nem tela de login.
Guia completo em **[docs/INSTALACAO.md](docs/INSTALACAO.md)**. Resumo:

```
git clone https://github.com/Strikedio/terminal-missao.git
cd terminal-missao
sudo ./instalacao/instalar_kiosk.sh meu_usuario
sudo reboot
```

Para desfazer: `sudo ./instalacao/instalar_kiosk.sh meu_usuario --remover`.

## Estrutura do projeto

```
terminal.py            interface (tela cheia), painel F12, atalhos
nucleo.py              regras dos modos, perfis, cronômetro (sem interface nem USB)
leitor_usb.py          detecção de pendrives (pendrive.key)
gravador.py            gravação dos pendrives
gravar_pendrive.py     gravador em linha de comando
sons.py                efeitos sonoros gerados por código
teste_console.py       joga qualquer modo pelo terminal de texto
testes_nucleo.py       testes das regras
testes_gravador.py     testes do gravador
instalacao/            instalar_kiosk.sh (modo quiosque no Debian)
docs/INSTALACAO.md     guia de instalação
```

Arquivos criados ao usar (ignorados pelo git): `config.json` (configurações e senha) e `logs/` (registro das missões).

## Testes

```
python testes_nucleo.py
python testes_gravador.py
python teste_console.py          # joga uma missão no terminal de texto
```

## Calibração

Tempos, tentativas e penalidades de cada dificuldade ficam no dicionário `PERFIS` em `nucleo.py`;
a penalidade de erro no desarme é `PENALIDADE_NS`. Ajuste conforme o ritmo do seu grupo.

## Licença

Ainda não definida. Adicione um arquivo `LICENSE` antes de abrir o projeto a terceiros.
