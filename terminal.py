"""TERMINAL DE MISSÃO - programa principal (tela cheia).

Rodar:
    python terminal.py            -> tela cheia (uso em campo)
    python terminal.py --janela   -> abre em janela (bom para a VM / testes)

Teclas do organizador (não aparecem na tela dos operadores):
    F12 (ou Ctrl+Shift+A)  painel do organizador (pede senha); dele se grava pendrives
    F5                     mostra/esconde a caixa para simular um pendrive digitando o nome
    F6                     avança a etapa manualmente (falha na porta USB)
Senha inicial: admin  (troque no painel!)
"""

import argparse
import json
import os
import subprocess
import sys
import time
import tkinter as tk

import gravador
import leitor_usb
import sons
from nucleo import FINAIS, MODOS, NS, PERFIS, Config, Missao

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_CFG = os.path.join(PASTA, "config.json")
PASTA_LOGS = os.path.join(PASTA, "logs")
PADRAO = {
    "modo": "campanha",
    "perfil": "normal",
    "qtd_pendrives": 3,
    "codigo_hack": "",
    "chave": 0,
    "tempo_s": 0,
    "senha": "admin",
}
GRACA_ADMIN_S = 60  # depois de digitar a senha, F5/F6 não pedem de novo por 60 s
FASES_COM_CODIGO = {
    "HACKING": "CÓDIGO >",
    "DECIFRAR": "MENSAGEM DECIFRADA >",
    "DEFESA": "CÓDIGO DE BLOQUEIO >",
}
PRESENCA = ("download", "controle")  # modos em que o pendrive precisa ficar conectado

BG, VERDE, VERM, AMBAR, CINZA = "#050805", "#33ff66", "#ff3333", "#ffb000", "#1c2a1c"
FONTE = "Consolas" if sys.platform.startswith("win") else "DejaVu Sans Mono"
NOME_MODO = {
    "campanha": "CAMPANHA COMPLETA",
    "hacking": "SÓ HACKING",
    "coleta": "SÓ COLETA",
    "desarme": "SÓ DESARME",
    "decifrar": "DECIFRAR MENSAGEM",
    "download": "TRANSFERÊNCIA DE DADOS",
    "defesa": "DEFESA DO SERVIDOR",
    "controle": "CONTROLE DE PONTO",
}
TEXTO_ESTADO = {
    "AGUARDANDO": ("AGUARDANDO", VERDE),
    "HACKING": ("INVASÃO EM ANDAMENTO", AMBAR),
    "DECIFRAR": ("MENSAGEM INTERCEPTADA", AMBAR),
    "COLETA": ("COLETA DE INFORMAÇÃO", AMBAR),
    "DESARME": ("OGIVA ARMADA - DESARME!", VERM),
    "DOWNLOAD": ("TRANSFERÊNCIA EM ANDAMENTO", AMBAR),
    "DEFESA": ("DEFENDA O SERVIDOR", AMBAR),
    "CONTROLE": ("DISPUTA PELO PONTO", AMBAR),
    "DESARMADO": ("OGIVA DESARMADA", VERDE),
    "DETONADO": ("DETONAÇÃO", VERM),
    "FALHOU": ("MISSÃO FALHOU", VERM),
    "CONCLUIDO": ("MISSÃO CONCLUÍDA", VERDE),
}
TAG_DO_SOM = {"ok": "ok", "vitoria": "ok", "erro": "erro", "explosao": "erro"}


def carregar_config():
    cfg = dict(PADRAO)
    try:
        with open(ARQ_CFG, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def salvar_config(cfg):
    try:
        with open(ARQ_CFG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def fmt_ns(ns):
    seg, resto = divmod(int(ns), NS)
    return f"{seg // 60:02d}:{seg % 60:02d}.{resto:09d}"


class App(tk.Tk):
    def __init__(self, teste=False, janela=False):
        super().__init__()
        self.title("Terminal de Missão")
        self.configure(bg=BG)
        if janela:
            self.geometry("1100x700")
        else:
            self.attributes("-fullscreen", True)
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # operador não fecha
        base = 14 if janela else max(12, self.winfo_screenheight() // 45)
        self.f = lambda k=1, neg=True: (FONTE, int(base * k), "bold" if neg else "normal")

        self.cfg = carregar_config()
        self.missao = None
        self.final = False
        self.som_fim_tocado = False
        self.arq_log = None
        self.monitor = leitor_usb.Monitor()
        self.presentes_reais = set()
        self.sim_presentes = set()
        self.contador = 0
        self.ultimo_seg = None
        self.overlay = None
        self.admin_ate = 0
        self.cod_visivel = True
        self.sim_visivel = False
        self.drives = []
        self.pedido_desligar = 0.0

        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)
        self._montar_espera()
        self._montar_missao()
        self._montar_admin()
        self._montar_grav()
        self.mostrar(self.f_espera)
        if teste:
            self._mostrar_sim()

        self.bind("<F12>", self.abrir_admin)
        self.bind("<Control-Shift-A>", self.abrir_admin)
        self.bind("<F5>", self.alternar_sim)
        self.bind("<F6>", self.avancar_manual)
        sons.preparar()
        self.after(200, self.tick)
        self.after(16, self.tick_cronometro)

    # ------------------------------------------------------------ telas
    def mostrar(self, frame):
        for fr in (self.f_espera, self.f_missao, self.f_admin, self.f_grav):
            fr.pack_forget()
        frame.pack(fill="both", expand=True)
        if frame is self.f_missao:
            self._foco()
        elif frame is self.f_admin:
            self._preencher_admin()
        elif frame is self.f_grav:
            self._preparar_grav()

    def _foco(self):
        (self.sim if self.sim_visivel else self.entrada).focus_set()

    def _montar_espera(self):
        fr = self.f_espera = tk.Frame(self.container, bg=BG)
        tk.Label(fr, text="TERMINAL DE MISSÃO", bg=BG, fg=VERDE, font=self.f(3)).pack(expand=True)
        tk.Label(
            fr,
            text="SISTEMA EM ESPERA\nAGUARDANDO ORDENS DO ORGANIZADOR",
            bg=BG,
            fg=AMBAR,
            font=self.f(1.5),
        ).pack(expand=True)

    def _montar_missao(self):
        fr = self.f_missao = tk.Frame(self.container, bg=BG)
        self.l_estado = tk.Label(fr, text="", bg=BG, fg=VERDE, font=self.f(2))
        self.l_estado.pack(pady=(12, 0))
        self.l_modo = tk.Label(fr, text="", bg=BG, fg=CINZA, font=self.f(0.8, False))
        self.l_modo.pack()
        f_tempo = tk.Frame(fr, bg=BG)
        f_tempo.pack(pady=(4, 0))
        self.l_tempo = tk.Label(f_tempo, text="00:00", width=5, bg=BG, fg=VERDE, font=self.f(6))
        self.l_tempo.pack(side="left")
        self.l_nano = tk.Label(
            f_tempo, text=".000000000", width=10, bg=BG, fg=VERDE, font=self.f(3), anchor="w"
        )
        self.l_nano.pack(side="left", anchor="s", pady=(0, 12))
        self.l_cap = tk.Label(fr, text="", bg=BG, fg=CINZA, font=self.f(0.8, False))
        self.l_cap.pack()
        self.l_ordem = tk.Label(fr, text="", bg=BG, fg=AMBAR, font=self.f(1.6))
        self.l_ordem.pack(pady=5)
        self.l_info = tk.Label(fr, text="", bg=BG, fg=VERDE, font=self.f(1, False))
        self.l_info.pack()

        self.log = tk.Text(
            fr,
            height=8,
            bg="#0a120a",
            fg=VERDE,
            font=self.f(1, False),
            state="disabled",
            relief="flat",
            highlightthickness=1,
            highlightbackground=CINZA,
            takefocus=0,
        )
        self.log.tag_config("ok", foreground=VERDE)
        self.log.tag_config("erro", foreground=VERM)
        self.log.tag_config("sis", foreground=AMBAR)
        self.log.pack(fill="both", expand=True, padx=30, pady=8)

        # parte de baixo: caixa de código (operador) e caixa de pendrive simulado (só F5)
        baixo = tk.Frame(fr, bg=BG)
        baixo.pack(fill="x", pady=(0, 8))
        baixo.columnconfigure(0, weight=1)
        self.f_cod = tk.Frame(baixo, bg=BG)
        self.f_cod.grid(row=0, column=0)
        self.l_prompt = tk.Label(self.f_cod, text="CÓDIGO >", bg=BG, fg=AMBAR, font=self.f(1.3))
        self.l_prompt.pack()
        self.entrada = tk.Entry(
            self.f_cod,
            bg="#0a120a",
            fg=VERDE,
            insertbackground=VERDE,
            font=self.f(1.6),
            justify="center",
            relief="flat",
            highlightthickness=2,
            highlightbackground=CINZA,
            highlightcolor=VERDE,
        )
        self.entrada.bind("<Return>", self.enviar_codigo)
        self.entrada.pack()
        self.f_sim = tk.Frame(baixo, bg=BG)
        self.f_sim.grid(row=1, column=0, pady=(8, 0))
        tk.Label(self.f_sim, text="pendrive >", bg=BG, fg=CINZA, font=self.f(0.9, False)).pack(
            side="left", padx=6
        )
        self.sim = tk.Entry(
            self.f_sim,
            bg="#0a120a",
            fg=AMBAR,
            insertbackground=AMBAR,
            font=self.f(1.2),
            justify="center",
            relief="flat",
        )
        self.sim.bind("<Return>", self.enviar_sim)
        self.sim.pack(side="left")
        self.f_sim.grid_remove()

    def _montar_admin(self):
        fr = self.f_admin = tk.Frame(self.container, bg=BG)
        tk.Label(fr, text="PAINEL DO ORGANIZADOR", bg=BG, fg=AMBAR, font=self.f(1.6)).pack(pady=8)
        corpo = tk.Frame(fr, bg=BG)
        corpo.pack()

        self.v_modo = tk.StringVar()
        self.v_perfil = tk.StringVar()
        self.v_qtd = tk.IntVar(value=3)
        self.v_codigo = tk.StringVar()
        self.v_chave = tk.IntVar(value=0)
        self.v_tempo = tk.IntVar(value=0)
        self.v_senha = tk.StringVar()

        def linha(r, texto, widget):
            tk.Label(
                corpo, text=texto, bg=BG, fg=VERDE, font=self.f(0.9), anchor="e", justify="right"
            ).grid(row=r, column=0, sticky="e", padx=10, pady=3)
            widget.grid(row=r, column=1, sticky="w", padx=10, pady=3)

        def menu(var, opcoes):
            om = tk.OptionMenu(corpo, var, *opcoes)
            om.config(
                bg="#0a120a",
                fg=VERDE,
                font=self.f(1),
                activebackground=CINZA,
                activeforeground=VERDE,
                highlightthickness=0,
                width=24,
            )
            om["menu"].config(bg="#0a120a", fg=VERDE, font=self.f(1))
            return om

        def entrada(var, largura=14, **kw):
            return tk.Entry(
                corpo,
                textvariable=var,
                width=largura,
                font=self.f(1),
                bg="#0a120a",
                fg=VERDE,
                insertbackground=VERDE,
                **kw,
            )

        def contador(var, a, b, inc=1):
            return tk.Spinbox(
                corpo,
                from_=a,
                to=b,
                increment=inc,
                textvariable=var,
                width=6,
                font=self.f(1),
                bg="#0a120a",
                fg=VERDE,
            )

        self.mapa_modo = {NOME_MODO[m]: m for m in MODOS}
        linha(0, "Modo de jogo:", menu(self.v_modo, list(self.mapa_modo)))
        linha(1, "Dificuldade:", menu(self.v_perfil, [p.upper() for p in PERFIS]))
        linha(2, "Pendrives (3 a 8):", contador(self.v_qtd, 3, 8))
        linha(3, "Código do hacking / palavra\n(vazio = sorteia):", entrada(self.v_codigo))
        linha(4, "Chave da cifra (0 = sorteia):", contador(self.v_chave, 0, 25))
        linha(
            5,
            "Tempo ou meta, em segundos\n(0 = padrão da dificuldade):",
            contador(self.v_tempo, 0, 3600, 10),
        )
        linha(6, "Nova senha (vazio = manter):", entrada(self.v_senha, show="*"))

        self.l_admin_info = tk.Label(
            fr, text="", bg=BG, fg=AMBAR, font=self.f(0.9, False), justify="left"
        )
        self.l_admin_info.pack(pady=6)

        def barra(botoes):
            b = tk.Frame(fr, bg=BG)
            b.pack(pady=3)
            for texto, cmd, cor in botoes:
                tk.Button(
                    b,
                    text=texto,
                    command=cmd,
                    bg=cor,
                    fg="black",
                    font=self.f(0.9),
                    relief="flat",
                    padx=10,
                    pady=4,
                    activebackground="white",
                ).pack(side="left", padx=5)

        barra(
            [
                ("SALVAR E INICIAR MISSÃO", lambda: self.admin_salvar(True), VERDE),
                ("SALVAR", lambda: self.admin_salvar(False), AMBAR),
                ("TESTAR PENDRIVES", self.admin_testar_usb, AMBAR),
            ]
        )
        barra(
            [
                ("GRAVAR PENDRIVES", lambda: self.mostrar(self.f_grav), VERDE),
                ("SIMULAR PENDRIVE (F5)", self.admin_sim, AMBAR),
                ("AVANÇAR ETAPA (F6)", self.admin_avancar, AMBAR),
            ]
        )
        ultima = [
            ("ABORTAR MISSÃO", self.admin_abortar, VERM),
            ("VOLTAR", self.admin_voltar, AMBAR),
        ]
        if sys.platform.startswith("linux"):
            ultima.append(("DESLIGAR NOTEBOOK", self.admin_desligar, VERM))
        ultima.append(("SAIR DO PROGRAMA", self.destroy, VERM))
        barra(ultima)

    def _montar_grav(self):
        fr = self.f_grav = tk.Frame(self.container, bg=BG)
        tk.Label(fr, text="GRAVAR PENDRIVES", bg=BG, fg=AMBAR, font=self.f(1.6)).pack(pady=(14, 4))
        tk.Label(
            fr,
            text="Conecte o pendrive, escolha o nome e grave.\n"
            "O nome é gravado no arquivo pendrive.key dentro dele.",
            bg=BG,
            fg=VERDE,
            font=self.f(0.9, False),
            justify="center",
        ).pack(pady=(0, 12))
        corpo = tk.Frame(fr, bg=BG)
        corpo.pack()
        self.v_drive = tk.StringVar()
        self.v_nome_grav = tk.StringVar(value=gravador.nomes_sugeridos()[0])

        tk.Label(corpo, text="Pendrive:", bg=BG, fg=VERDE, font=self.f(1)).grid(
            row=0, column=0, sticky="e", padx=10, pady=6
        )
        self.om_drive = tk.OptionMenu(corpo, self.v_drive, "")
        self.om_drive.config(
            bg="#0a120a",
            fg=VERDE,
            font=self.f(0.9),
            activebackground=CINZA,
            activeforeground=VERDE,
            highlightthickness=0,
            width=48,
        )
        self.om_drive["menu"].config(bg="#0a120a", fg=VERDE, font=self.f(0.9))
        self.om_drive.grid(row=0, column=1, sticky="w", padx=10, pady=6)

        tk.Label(corpo, text="Nome:", bg=BG, fg=VERDE, font=self.f(1)).grid(
            row=1, column=0, sticky="e", padx=10, pady=6
        )
        linha_nome = tk.Frame(corpo, bg=BG)
        linha_nome.grid(row=1, column=1, sticky="w", padx=10, pady=6)
        tk.Entry(
            linha_nome,
            textvariable=self.v_nome_grav,
            width=14,
            font=self.f(1.2),
            bg="#0a120a",
            fg=VERDE,
            insertbackground=VERDE,
        ).pack(side="left")
        om_nome = tk.OptionMenu(linha_nome, self.v_nome_grav, *gravador.nomes_sugeridos())
        om_nome.config(
            bg="#0a120a",
            fg=VERDE,
            font=self.f(0.9),
            activebackground=CINZA,
            activeforeground=VERDE,
            highlightthickness=0,
        )
        om_nome["menu"].config(bg="#0a120a", fg=VERDE, font=self.f(0.9))
        om_nome.pack(side="left", padx=8)

        self.l_grav = tk.Label(
            fr, text="", bg=BG, fg=AMBAR, font=self.f(1, False), justify="center"
        )
        self.l_grav.pack(pady=14)
        tk.Label(
            fr,
            text="ISCA = pendrive falso. VERMELHO e AZUL = modo Controle de ponto.\n"
            "Depois de gravar, o nome seguinte da lista já fica selecionado.",
            bg=BG,
            fg=CINZA,
            font=self.f(0.8, False),
            justify="center",
        ).pack()
        botoes = tk.Frame(fr, bg=BG)
        botoes.pack(pady=14)
        for texto, comando, cor in (
            ("GRAVAR NO PENDRIVE", self.grav_gravar, VERDE),
            ("ATUALIZAR LISTA", self._atualizar_drives, AMBAR),
            ("VOLTAR", lambda: self.mostrar(self.f_admin), AMBAR),
        ):
            tk.Button(
                botoes,
                text=texto,
                command=comando,
                bg=cor,
                fg="black",
                font=self.f(1),
                relief="flat",
                padx=12,
                pady=6,
                activebackground="white",
            ).pack(side="left", padx=6)

    def _preparar_grav(self):
        self.l_grav.config(text="", fg=AMBAR)
        self._atualizar_drives()

    def _atualizar_drives(self, manter=None):
        """Relê os pendrives conectados; mantém a seleção em `manter` (caminho) se ainda existir."""
        self.drives = gravador.listar_pendrives()
        textos = [gravador.descrever(d) for d in self.drives]
        menu = self.om_drive["menu"]
        menu.delete(0, "end")
        for texto in textos or ["(nenhum pendrive detectado)"]:
            menu.add_command(label=texto, command=lambda t=texto: self.v_drive.set(t))
        escolhido = next(
            (gravador.descrever(d) for d in self.drives if d["caminho"] == manter), None
        )
        self.v_drive.set(escolhido or (textos[0] if textos else "(nenhum pendrive detectado)"))

    def _auto_atualizar_drives(self):
        """Na tela de gravação, atualiza a lista sozinho quando um pendrive entra ou sai."""
        atuais = gravador.listar_pendrives()
        if [d["caminho"] for d in atuais] == [d["caminho"] for d in self.drives]:
            return
        selecionado = next(
            (d["caminho"] for d in self.drives if gravador.descrever(d) == self.v_drive.get()),
            None,
        )
        self._atualizar_drives(manter=selecionado)

    def grav_gravar(self):
        item = next((d for d in self.drives if gravador.descrever(d) == self.v_drive.get()), None)
        if item is None:
            self.l_grav.config(
                text="Nenhum pendrive selecionado.\n" "Conecte um e clique em ATUALIZAR LISTA.",
                fg=VERM,
            )
            sons.tocar("erro")
            return
        ok, mensagem = gravador.gravar(item["caminho"], self.v_nome_grav.get())
        self.l_grav.config(
            text=("GRAVADO: " if ok else "ERRO: ") + mensagem, fg=VERDE if ok else VERM
        )
        sons.tocar("ok" if ok else "erro")
        if ok:
            self.v_nome_grav.set(gravador.proximo_nome(self.v_nome_grav.get()))
        self.monitor = leitor_usb.Monitor()  # a gravação não pode contar como inserção na missão
        self._atualizar_drives(manter=item["caminho"])

    def _preencher_admin(self):
        c = self.cfg
        self.v_modo.set(NOME_MODO.get(c["modo"], NOME_MODO["campanha"]))
        self.v_perfil.set(c["perfil"].upper())
        self.v_qtd.set(c["qtd_pendrives"])
        self.v_codigo.set(c["codigo_hack"])
        self.v_chave.set(c["chave"])
        self.v_tempo.set(c["tempo_s"])
        self.v_senha.set("")
        self._atualizar_info_admin()

    def _atualizar_info_admin(self, extra=""):
        txt = ""
        if self.missao:
            txt = f"MISSÃO EM CURSO ({self.missao.estado})\n{self.missao.resumo_admin()}\n"
        self.l_admin_info.config(text=txt + extra)

    # ------------------------------------------------------------ senha e atalhos
    def _pedir_senha(self, callback):
        if self.overlay is not None:
            return
        ov = self.overlay = tk.Frame(self, bg=BG, highlightthickness=2, highlightbackground=AMBAR)
        ov.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(ov, text="SENHA DO ORGANIZADOR", bg=BG, fg=AMBAR, font=self.f(1.3)).pack(
            padx=30, pady=(20, 8)
        )
        ent = tk.Entry(
            ov,
            show="*",
            font=self.f(1.4),
            bg="#0a120a",
            fg=VERDE,
            insertbackground=VERDE,
            justify="center",
        )
        ent.pack(padx=30, pady=8)
        aviso = tk.Label(
            ov, text="Enter = entrar | Esc = cancelar", bg=BG, fg=CINZA, font=self.f(0.8, False)
        )
        aviso.pack(pady=(0, 16))
        ent.focus_set()

        def fechar():
            ov.destroy()
            self.overlay = None
            if self.missao and self.f_missao.winfo_ismapped():
                self._foco()

        def validar(_e=None):
            if ent.get() == self.cfg["senha"]:
                self.admin_ate = time.monotonic() + GRACA_ADMIN_S
                fechar()
                callback()
            else:
                aviso.config(text="SENHA INCORRETA", fg=VERM)
                ent.delete(0, "end")

        ent.bind("<Return>", validar)
        ent.bind("<Escape>", lambda _e: fechar())

    def _exigir_admin(self, callback):
        if time.monotonic() < self.admin_ate:
            callback()
        else:
            self._pedir_senha(callback)

    def abrir_admin(self, _e=None):
        self._pedir_senha(lambda: self.mostrar(self.f_admin))  # F12 sempre pede a senha

    def alternar_sim(self, _e=None):
        if not self.missao:
            return
        if self.sim_visivel:
            self._ocultar_sim()
        else:
            self._exigir_admin(self._mostrar_sim)

    def _mostrar_sim(self):
        self.sim_visivel = True
        self.f_sim.grid()
        self.sim.focus_set()

    def _ocultar_sim(self):
        self.sim_visivel = False
        self.f_sim.grid_remove()
        self.entrada.focus_set()

    def avancar_manual(self, _e=None):
        if self.missao and not self.final:
            self._exigir_admin(self._avancar)

    def _avancar(self):
        if self.missao and not self.final:
            self._processar("ORGANIZADOR", self.missao.avancar_etapa())
            self._drenar_eventos()

    # ------------------------------------------------------------ painel do organizador
    def admin_salvar(self, iniciar):
        try:
            novo = {
                "modo": self.mapa_modo[self.v_modo.get()],
                "perfil": self.v_perfil.get().lower(),
                "qtd_pendrives": int(self.v_qtd.get()),
                "codigo_hack": self.v_codigo.get().strip().upper(),
                "chave": int(self.v_chave.get()),
                "tempo_s": int(self.v_tempo.get()),
                "senha": self.v_senha.get() or self.cfg["senha"],
            }
            Config(
                modo=novo["modo"],
                perfil=novo["perfil"],
                qtd_pendrives=novo["qtd_pendrives"],
                codigo_hack=novo["codigo_hack"],
                chave=novo["chave"],
                tempo_s=novo["tempo_s"],
            )  # só valida
            if len(novo["senha"]) < 4:
                raise ValueError("A senha deve ter pelo menos 4 caracteres.")
        except (ValueError, tk.TclError, KeyError) as e:
            self._atualizar_info_admin(f"\nCONFIGURAÇÃO INVÁLIDA: {e}")
            return
        self.cfg = novo
        salvar_config(self.cfg)
        if iniciar:
            self.iniciar_missao()
        else:
            self._atualizar_info_admin("\nConfiguração salva.")

    def admin_testar_usb(self):
        achados = leitor_usb.ler_pendrives()
        if not achados:
            self._atualizar_info_admin("\nNenhum pendrive de missão detectado agora.")
        else:
            linhas = "\n".join(f"  {c}  ->  {n}" for c, n in achados.items())
            self._atualizar_info_admin(f"\nPendrives detectados:\n{linhas}")

    def admin_sim(self):
        if not self.missao:
            self._atualizar_info_admin("\nInicie uma missão primeiro.")
            return
        self._mostrar_sim()
        self.mostrar(self.f_missao)

    def admin_avancar(self):
        if not self.missao or self.final:
            self._atualizar_info_admin("\nNão há missão em andamento.")
            return
        self._avancar()
        self.mostrar(self.f_missao)

    def admin_abortar(self):
        self._fechar_log("MISSÃO ABORTADA PELO ORGANIZADOR")
        self.missao = None
        self.final = False
        self.sim_presentes.clear()
        self.mostrar(self.f_espera)

    def admin_voltar(self):
        self.mostrar(self.f_missao if self.missao else self.f_espera)

    def admin_desligar(self):
        """Desliga o notebook (Linux). Pede um segundo clique em até 5 s para confirmar."""
        agora = time.monotonic()
        if agora - self.pedido_desligar > 5:
            self.pedido_desligar = agora
            self._atualizar_info_admin(
                "\nClique de novo em DESLIGAR NOTEBOOK em até 5 s para confirmar."
            )
            return
        self._fechar_log("NOTEBOOK DESLIGADO PELO ORGANIZADOR")
        try:
            resultado = subprocess.run(
                ["systemctl", "poweroff"], capture_output=True, text=True, timeout=15, check=False
            )
        except (OSError, subprocess.SubprocessError) as erro:
            self._atualizar_info_admin(f"\nNão foi possível desligar: {erro}")
            return
        if resultado.returncode != 0:
            self._atualizar_info_admin(f"\nNão foi possível desligar: {resultado.stderr.strip()}")

    # ------------------------------------------------------------ missão
    def iniciar_missao(self):
        self._fechar_log()
        c = self.cfg
        self.missao = Missao(
            Config(
                modo=c["modo"],
                perfil=c["perfil"],
                qtd_pendrives=c["qtd_pendrives"],
                codigo_hack=c["codigo_hack"],
                chave=c["chave"],
                tempo_s=c["tempo_s"],
            )
        )
        self.final = False
        self.som_fim_tocado = False
        self.ultimo_seg = None
        self.sim_presentes.clear()
        self.monitor = leitor_usb.Monitor()  # o que já está plugado não conta como inserção
        try:
            os.makedirs(PASTA_LOGS, exist_ok=True)
            nome = time.strftime("missao_%Y%m%d_%H%M%S.txt")
            self.arq_log = open(os.path.join(PASTA_LOGS, nome), "w", encoding="utf-8")
        except OSError:
            self.arq_log = None
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")
        self.missao.iniciar()
        m = self.missao
        self.registrar(
            "SISTEMA",
            f"Missão iniciada: {NOME_MODO[c['modo']]} | {c['perfil'].upper()} | "
            f"{len(m.nomes)} pendrives",
            "sis",
        )
        self.registrar("SISTEMA", "[SOLUÇÃO] " + m.resumo_admin().replace("\n", " | "), "sis")
        sons.tocar("alarme")
        self.mostrar(self.f_missao)

    def _fechar_log(self, motivo=None):
        if self.arq_log:
            if motivo:
                self.arq_log.write(f"[{time.strftime('%H:%M:%S')}] SISTEMA: {motivo}\n")
            self.arq_log.close()
            self.arq_log = None

    def registrar(self, origem, texto, tag="sis"):
        linha = f"[{time.strftime('%H:%M:%S')}] {origem}: {texto}\n"
        if "[SOLUÇÃO]" not in texto:  # a solução fica só no arquivo de log, nunca na tela
            self.log.config(state="normal")
            self.log.insert("end", linha, tag)
            self.log.see("end")
            self.log.config(state="disabled")
        if self.arq_log:
            self.arq_log.write(linha)
            self.arq_log.flush()

    def _som_e_tag(self, texto):
        m, t = self.missao, texto.upper()
        if m.estado in ("DESARMADO", "CONCLUIDO"):
            return "vitoria", "ok"
        if m.estado == "DETONADO":
            return "explosao", "erro"
        if m.estado == "FALHOU":
            return "erro", "erro"
        if t.startswith("ERRO") or any(
            p in t for p in ("CORROMPIDO", "NEGADO", "INCORRET", "INVÁLID")
        ):
            return "erro", "erro"
        if "JÁ " in t or "NENHUM" in t or "NÃO PODE" in t:
            return "beep", "sis"
        return "ok", "ok"

    def _processar(self, origem, texto):
        som, tag = self._som_e_tag(texto)
        if self.missao.estado in FINAIS:
            self.som_fim_tocado = True
        self.registrar(origem, texto, tag)
        sons.tocar(som)

    def _drenar_eventos(self):
        """Mensagens geradas pelo próprio tempo (intrusões, transferências, mudança de dono do ponto...)."""
        for texto, som in self.missao.pop_eventos():
            self.registrar("SISTEMA", texto, TAG_DO_SOM.get(som, "sis"))
            if self.missao.estado not in FINAIS:
                sons.tocar(som)

    def enviar_codigo(self, _e=None):
        txt = self.entrada.get().strip().upper()
        self.entrada.delete(0, "end")
        if not txt or not self.missao or self.final:
            return
        self.registrar("OPERADOR", txt, "sis")
        self._processar("SISTEMA", self.missao.tentar_codigo(txt))
        self._drenar_eventos()

    def enviar_sim(self, _e=None):
        nome = self.sim.get().strip().upper()
        self.sim.delete(0, "end")
        if not nome or not self.missao or self.final:
            return
        m = self.missao
        if (
            m.cfg.modo in PRESENCA and nome in self.sim_presentes
        ):  # digitar de novo = "tirar" o pendrive
            self.sim_presentes.discard(nome)
            self.registrar(f"PENDRIVE {nome}", "removido (simulado)", "sis")
            return
        if m.cfg.modo in PRESENCA:
            self.sim_presentes.add(nome)
        self._processar(f"PENDRIVE {nome}", m.inserir_pendrive(nome))
        self._drenar_eventos()

    # ------------------------------------------------------------ laços
    def tick(self):
        """Lógica da missão: 5 vezes por segundo."""
        try:
            self.contador += 1
            m = self.missao
            if self.contador % 5 == 0 and self.f_grav.winfo_ismapped():
                self._auto_atualizar_drives()
            if m:
                if self.contador % 3 == 0:  # lê os pendrives ~ a cada 0,6 s
                    if self.f_grav.winfo_ismapped():  # gravando pendrives: não conta como inserção
                        self.monitor = leitor_usb.Monitor()
                    novos, self.presentes_reais = self.monitor.varrer()
                    if not self.final:
                        for nome in novos:
                            self._processar(f"PENDRIVE {nome}", m.inserir_pendrive(nome))
                if not self.final:
                    m.definir_presentes(self.presentes_reais | self.sim_presentes)
                    m.verificar_tempo()
                    self._drenar_eventos()
                self._atualizar_tela()
                self._beep_contagem()
                if m.estado in FINAIS and not self.final:
                    self._finalizar()
        except Exception as e:  # o jogo nunca pode travar em campo
            print("Erro no laço:", e, file=sys.stderr)
        finally:
            self.after(200, self.tick)

    def tick_cronometro(self):
        """Cronômetro em nanossegundos: redesenhado ~60 vezes por segundo."""
        try:
            m = self.missao
            if m:
                ns, regressivo = m.cronometro()
                seg, resto = divmod(ns, NS)
                self.l_tempo.config(text=f"{seg // 60:02d}:{seg % 60:02d}")
                self.l_nano.config(text=f".{resto:09d}")
                if self.final:
                    cor = VERDE if m.estado in ("DESARMADO", "CONCLUIDO") else VERM
                    legenda = "CRONÔMETRO PARADO"
                else:
                    cor = VERM if regressivo and ns <= 30 * NS else (AMBAR if regressivo else VERDE)
                    legenda = "TEMPO RESTANTE" if regressivo else "TEMPO DECORRIDO"
                self.l_tempo.config(fg=cor)
                self.l_nano.config(fg=cor)
                self.l_cap.config(text=legenda)
        except Exception as e:
            print("Erro no cronômetro:", e, file=sys.stderr)
        finally:
            self.after(16, self.tick_cronometro)

    def _mostrar_cod(self, visivel):
        if visivel == self.cod_visivel:
            return
        self.cod_visivel = visivel
        if visivel:
            self.f_cod.grid()
            self._foco()
        else:
            self.f_cod.grid_remove()

    def _atualizar_tela(self):
        m = self.missao
        p = m.painel()
        self.l_modo.config(text=f"{NOME_MODO[m.cfg.modo]} | {m.cfg.perfil.upper()}")
        self.l_ordem.config(text=p["ordem"], fg=VERM if p["alerta"] else AMBAR)
        if m.estado in FINAIS:
            texto = m.msg_final or TEXTO_ESTADO[m.estado][0]
            cor = VERDE if m.estado in ("DESARMADO", "CONCLUIDO") else VERM
            self.l_info.config(text="AGUARDE INSTRUÇÕES DO ORGANIZADOR")
        else:
            texto, cor = TEXTO_ESTADO.get(m.estado, (m.estado, VERDE))
            if p["alerta"]:
                cor = VERM
            self.l_info.config(text=p["info"])
        self.l_estado.config(text=texto, fg=cor)
        com_codigo = m.fase in FASES_COM_CODIGO and m.estado not in FINAIS
        if com_codigo:
            self.l_prompt.config(text=FASES_COM_CODIGO[m.fase])
        self._mostrar_cod(com_codigo)

    def _beep_contagem(self):
        m = self.missao
        if self.final:
            return
        ns, regressivo = m.cronometro()
        if regressivo:
            seg = ns // NS
            if seg != self.ultimo_seg and seg <= 10:
                sons.tocar("beep")
            self.ultimo_seg = seg

    def _finalizar(self):
        self.final = True
        m = self.missao
        som, tag = self._som_e_tag("")
        if not self.som_fim_tocado:  # se o fim veio de uma ação, o som já tocou
            sons.tocar(som)
        ns, _ = m.cronometro()
        self.registrar(
            "SISTEMA",
            f"FIM DA MISSÃO: {m.msg_final or m.estado} | cronômetro parado em "
            f"{fmt_ns(ns)} | erros={m.erros} | tentativas={m.tentativas}",
            tag,
        )
        self._atualizar_tela()
        self._fechar_log()
        if self.sim_visivel:
            self._ocultar_sim()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teste", action="store_true", help="já abre com a caixa de pendrive simulado")
    ap.add_argument("--janela", action="store_true", help="abre em janela, não em tela cheia")
    a = ap.parse_args()
    App(teste=a.teste, janela=a.janela).mainloop()


if __name__ == "__main__":
    main()
