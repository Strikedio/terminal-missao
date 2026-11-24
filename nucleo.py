"""Núcleo do jogo: só lógica, sem tela e sem USB.

A tela (terminal.py) e o leitor de pendrives apenas CHAMAM estas funções.
Todo o tempo é medido em NANOSSEGUNDOS inteiros e o relógio pode ser trocado
(parâmetro `relogio`), o que permite testar tudo sem esperar.

Modos: campanha, hacking, coleta, desarme, decifrar, download, defesa, controle.
"""

import random
import time
from dataclasses import dataclass

NS = 1_000_000_000
NOMES_PENDRIVES = ["ALFA", "BRAVO", "CHARLIE", "DELTA", "ECO", "FOXTROT", "GOLF", "HOTEL"]
EQUIPES = ("VERMELHO", "AZUL")  # pendrives do modo "controle"
MODOS = ("campanha", "hacking", "coleta", "desarme", "decifrar", "download", "defesa", "controle")
FINAIS = ("DESARMADO", "DETONADO", "FALHOU", "CONCLUIDO")
DURACAO_MAX_S = 180 * 60  # duração máxima que o organizador pode definir (3 horas)
PENALIDADE_NS = 15 * NS  # tempo perdido a cada erro no desarme
PALAVRAS = [
    "ESCUDO",
    "FALCAO",
    "TROVAO",
    "ECLIPSE",
    "SENTINELA",
    "VIPER",
    "CORVO",
    "ZENITE",
    "ATLAS",
    "FENIX",
    "RADAR",
    "ALVORADA",
]
ALFABETO_CODIGOS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem O/0/I/1 para não confundir

# Perfis de dificuldade (o organizador escolhe um deles)
PERFIS = {
    "treino": {
        "erros": 5,
        "seg_por_pendrive": 180,
        "tentativas": 10,
        "reinicia": False,
        "dl_seg": 20,
        "dl_limite": 120,
        "def_duracao": 180,
        "def_intervalo": 25,
        "def_janela": 15,
        "def_integridade": 5,
        "ctl_meta": 60,
    },
    "normal": {
        "erros": 3,
        "seg_por_pendrive": 120,
        "tentativas": 6,
        "reinicia": False,
        "dl_seg": 35,
        "dl_limite": 90,
        "def_duracao": 300,
        "def_intervalo": 18,
        "def_janela": 10,
        "def_integridade": 3,
        "ctl_meta": 120,
    },
    "elite": {
        "erros": 2,
        "seg_por_pendrive": 75,
        "tentativas": 4,
        "reinicia": True,
        "dl_seg": 50,
        "dl_limite": 70,
        "def_duracao": 420,
        "def_intervalo": 12,
        "def_janela": 7,
        "def_integridade": 2,
        "ctl_meta": 180,
    },
}


def cesar(texto, chave):
    """Cifra de César: desloca cada letra A-Z 'chave' posições para a frente."""
    return "".join(
        chr((ord(c) - 65 + chave) % 26 + 65) if "A" <= c <= "Z" else c for c in texto.upper()
    )


@dataclass
class Config:
    modo: str = "campanha"
    perfil: str = "normal"
    qtd_pendrives: int = 3  # o organizador escolhe de 3 a 8
    codigo_hack: str = ""  # vazio = sorteia (4 dígitos; palavra no modo decifrar)
    chave: int = 0  # chave da cifra (modo decifrar); 0 = sorteia
    tempo_s: int = 0  # 0 = padrão do perfil; senão: tempo/meta em segundos
    duracao_s: int = 0  # duração total da missão em segundos (0 = padrão da dificuldade)

    def __post_init__(self):
        if self.modo not in MODOS:
            raise ValueError(f"Modo inválido: {self.modo}")
        if self.perfil not in PERFIS:
            raise ValueError(f"Perfil inválido: {self.perfil}")
        if not 3 <= self.qtd_pendrives <= 8:
            raise ValueError("A quantidade de pendrives deve ser de 3 a 8.")
        if not 0 <= self.chave <= 25:
            raise ValueError("A chave da cifra deve ser de 0 a 25.")
        if not 0 <= self.tempo_s <= 3600:
            raise ValueError("O tempo deve ser de 0 a 3600 segundos.")
        if not 0 <= self.duracao_s <= DURACAO_MAX_S:
            raise ValueError("A duração deve ser de 0 a 180 minutos.")
        self.codigo_hack = (self.codigo_hack or "").strip().upper()
        if self.modo == "decifrar":
            if not self.codigo_hack:
                self.codigo_hack = random.choice(PALAVRAS)
            elif not (self.codigo_hack.isascii() and self.codigo_hack.isalpha()):
                raise ValueError("A palavra secreta deve ter só letras, sem acento.")
            if not self.chave:
                self.chave = random.randint(1, 25)
        elif not self.codigo_hack:
            self.codigo_hack = "".join(random.choice("0123456789") for _ in range(4))


class Missao:
    def __init__(self, config, relogio=time.perf_counter_ns):
        self.cfg = config
        self.p = PERFIS[config.perfil]
        self.relogio = relogio  # relógio injetável (ns inteiros): facilita testar
        self.estado = "AGUARDANDO"  # etapa atual (ou resultado final)
        self.fase = "AGUARDANDO"  # última etapa ativa (não muda quando a missão acaba)
        self.msg_final = ""
        self.vencedor = None
        self.nomes = NOMES_PENDRIVES[: config.qtd_pendrives]
        self.ordem = random.sample(self.nomes, len(self.nomes))  # ordem secreta do desarme
        self.ordem_revelada = False
        self.tentativas = 0
        self.erros = 0
        self.progresso = []  # pendrives já aceitos/coletados/transferidos
        self.fim = None  # instante em que a contagem regressiva acaba
        self.t0 = None
        self._ultimo = None
        self._congelado = None  # cronômetro parado ao fim da missão
        self.presentes = set()  # pendrives conectados agora
        self.eventos = []  # (texto, som) gerados pelo tempo, lidos pela tela
        # decifrar
        self.chave = config.chave
        self.cifrado = cesar(config.codigo_hack, config.chave) if config.modo == "decifrar" else ""
        # download
        self.dl_meta = self.p["dl_seg"] * NS
        self.acum = {n: 0 for n in self.nomes}
        self._ativos = set()
        # defesa
        self.integ_max = self.p["def_integridade"]
        self.integridade = self.integ_max
        self.ataque = None
        self.bloqueios = 0
        self._prox_ataque = None
        # controle
        self.ctl_meta = (config.tempo_s or self.p["ctl_meta"]) * NS
        self.acum_eq = {e: 0 for e in EQUIPES}
        self.dono = None

    # ---------- utilidades ----------
    def _set(self, estado):
        self.estado = self.fase = estado

    def _fim(self, estado, msg):
        """Encerra a missão e PARA o cronômetro."""
        if self.estado in FINAIS:
            return
        self._congelado = self._crono_vivo()
        self.estado = estado
        self.msg_final = msg
        self.ataque = None

    def _crono_vivo(self):
        agora = self.relogio()
        if self.fim is not None:
            return max(0, self.fim - agora), True
        if self.t0 is not None:
            return agora - self.t0, False
        return 0, False

    def cronometro(self):
        """(nanossegundos, regressivo?). Regressivo = tempo restante; senão = tempo decorrido."""
        return self._congelado if self._congelado is not None else self._crono_vivo()

    def pop_eventos(self):
        ev, self.eventos = self.eventos, []
        return ev

    def definir_presentes(self, nomes):
        self.presentes = {n.strip().upper() for n in nomes}

    # ---------- controle da missão ----------
    def iniciar(self):
        self.t0 = self._ultimo = agora = self.relogio()
        m, tempo = self.cfg.modo, self.cfg.duracao_s or self.cfg.tempo_s
        if m in ("campanha", "hacking"):
            self._set("HACKING")
        elif m == "decifrar":
            self._set("DECIFRAR")
        elif m == "coleta":
            self._set("COLETA")
        elif m == "desarme":
            self.ordem_revelada = True  # desarme sozinho: a ordem já aparece
            self._iniciar_desarme()
        elif m == "download":
            self._set("DOWNLOAD")
            if tempo:
                self.dl_meta = max(NS, tempo * NS // len(self.nomes))  # tempo total / pendrives
            self.fim = agora + (tempo or self.p["dl_limite"] * len(self.nomes)) * NS
        elif m == "defesa":
            self._set("DEFESA")
            self.fim = agora + (tempo or self.p["def_duracao"]) * NS
            self._agendar(agora)
        elif m == "controle":
            self._set("CONTROLE")
        if self.cfg.duracao_s and self.fim is None:
            # hacking, decifrar, coleta, controle e campanha: prazo total da missão
            self.fim = agora + self.cfg.duracao_s * NS

    def _iniciar_desarme(self):
        self._set("DESARME")
        self.progresso = []
        if self.cfg.modo == "campanha" and self.cfg.duracao_s:
            return  # na campanha o prazo é um só, contado desde o início da missão
        total = (
            self.cfg.duracao_s or self.cfg.tempo_s or self.p["seg_por_pendrive"] * len(self.nomes)
        )
        self.fim = self.relogio() + total * NS

    def verificar_tempo(self):
        """Avança o relógio da missão (chamado várias vezes por segundo pela tela)."""
        if self.estado == "AGUARDANDO" or self.estado in FINAIS:
            return
        agora = self.relogio()
        dt = max(0, agora - self._ultimo)
        self._ultimo = agora
        if self.fim is not None and agora >= self.fim:
            if self.estado == "DESARME":
                self._fim("DETONADO", "DETONAÇÃO")
            elif self.estado == "DOWNLOAD":
                self._fim("FALHOU", "TEMPO ESGOTADO")
                self.eventos.append(("Tempo esgotado. Transferência incompleta.", "erro"))
            elif self.estado == "DEFESA":
                self._fim("CONCLUIDO", "DEFESA BEM-SUCEDIDA")
                self.eventos.append(("Tempo cumprido. SERVIDOR PROTEGIDO!", "vitoria"))
            elif self.estado == "CONTROLE":
                self._fim_controle_por_tempo()
            else:  # hacking, decifrar, coleta
                self._fim("FALHOU", "TEMPO ESGOTADO")
                self.eventos.append(("Tempo esgotado. Missão fracassada.", "explosao"))
            return
        if self.estado == "DOWNLOAD":
            self._tick_download(dt)
        elif self.estado == "DEFESA":
            self._tick_defesa(agora)
        elif self.estado == "CONTROLE":
            self._tick_controle(dt)

    # ---------- modos com código: HACKING e DECIFRAR ----------
    def tentar_codigo(self, codigo):
        codigo = codigo.strip().upper()
        self.verificar_tempo()
        if self.estado in ("HACKING", "DECIFRAR"):
            return self._tentativa(codigo)
        if self.estado == "DEFESA":
            return self._bloquear(codigo)
        return "Nenhuma invasão em andamento."

    def _tentativa(self, codigo):
        self.tentativas += 1
        if codigo == self.cfg.codigo_hack:
            return self._acesso()
        certos = sum(a == b for a, b in zip(codigo, self.cfg.codigo_hack))
        decifrar = self.estado == "DECIFRAR"
        if self.tentativas >= self.p["tentativas"]:
            self._fim("FALHOU", "SISTEMA BLOQUEADO")
            return "SISTEMA BLOQUEADO. Missão falhou."
        restam = self.p["tentativas"] - self.tentativas
        if decifrar:
            return f"Mensagem INCORRETA. Letras certas na posição certa: {certos}. Tentativas restantes: {restam}."
        return f"Acesso negado. Dígitos certos na posição certa: {certos}. Tentativas restantes: {restam}."

    def _acesso(self):
        if self.estado == "DECIFRAR":
            self._fim("CONCLUIDO", "MENSAGEM DECIFRADA")
            return "MENSAGEM DECIFRADA. Missão cumprida."
        self.ordem_revelada = True
        if self.cfg.modo == "campanha":
            self._iniciar_desarme()
            return "ACESSO CONCEDIDO. Ordem dos pendrives revelada. CONTAGEM INICIADA!"
        self._fim("CONCLUIDO", "INVASÃO CONCLUÍDA")
        return "ACESSO CONCEDIDO. Invasão concluída."

    # ---------- pendrives ----------
    def inserir_pendrive(self, nome):
        nome = nome.strip().upper()
        self.verificar_tempo()
        e = self.estado
        if e == "COLETA":
            return self._coleta(nome)
        if e == "DESARME":
            return self._desarme(nome)
        if e == "DOWNLOAD":
            return self._download_insercao(nome)
        if e == "CONTROLE":
            if nome in EQUIPES:
                return f"Chave {nome} detectada."
            return "CHAVE INVÁLIDA. Pendrive não reconhecido."
        return "Nenhuma missão aceitando pendrives agora."

    def _coleta(self, nome):
        if nome not in self.nomes:
            return "ARQUIVO CORROMPIDO. Pendrive desconhecido (isca?)."
        if nome in self.progresso:
            return f"{nome} já foi coletado."
        self.progresso.append(nome)
        if len(self.progresso) == len(self.nomes):
            self._fim("CONCLUIDO", "INFORMAÇÕES RECUPERADAS")
            return f"{nome} coletado. TODAS AS INFORMAÇÕES RECUPERADAS."
        return f"{nome} coletado ({len(self.progresso)}/{len(self.nomes)})."

    def _desarme(self, nome):
        if nome in self.progresso:
            return f"{nome} já está inserido."
        if nome == self.ordem[len(self.progresso)]:
            self.progresso.append(nome)
            if len(self.progresso) == len(self.ordem):
                self._fim("DESARMADO", "OGIVA DESARMADA")
                return "SEQUÊNCIA COMPLETA. OGIVA DESARMADA!"
            return f"{nome} aceito ({len(self.progresso)}/{len(self.ordem)})."
        return self._erro(nome)

    def _erro(self, nome):
        self.erros += 1
        self.fim -= PENALIDADE_NS
        texto = f"ERRO: {nome} fora de ordem ou inválido. -{PENALIDADE_NS // NS}s."
        if self.p["reinicia"]:
            self.progresso = []
            texto += " Sequência reiniciada!"
        if self.erros > self.p["erros"] or self.fim <= self.relogio():
            self._fim("DETONADO", "DETONAÇÃO")
            texto += " DETONAÇÃO!"
        return texto

    # ---------- modo DOWNLOAD (manter o pendrive conectado) ----------
    def _download_insercao(self, nome):
        if nome not in self.nomes:
            self.erros += 1
            texto = "ERRO: ARQUIVO CORROMPIDO. Pendrive desconhecido (isca?)."
            if self.erros > self.p["erros"]:
                self._fim("FALHOU", "ALARME DISPARADO")
                texto += " ALARME DISPARADO!"
            return texto
        if nome in self.progresso:
            return f"{nome} já foi transferido."
        return f"{nome}: transferência iniciada. NÃO REMOVA O PENDRIVE!"

    def _tick_download(self, dt):
        validos = {n for n in self.nomes if n not in self.progresso}
        agora_ativos = validos & self.presentes
        for n in sorted(self._ativos - agora_ativos):  # removidos
            if self.p["reinicia"]:
                self.acum[n] = 0
                self.eventos.append((f"ERRO: {n} desconectado. Transferência REINICIADA!", "erro"))
            else:
                pct = self.acum[n] * 100 // self.dl_meta
                self.eventos.append(
                    (f"ERRO: {n} desconectado. Transferência pausada em {pct}%.", "erro")
                )
        self._ativos = agora_ativos
        for n in self.nomes:
            if n in agora_ativos:
                self.acum[n] += dt
                if self.acum[n] >= self.dl_meta:
                    self._completar_download(n)
                    if self.estado in FINAIS:
                        return

    def _completar_download(self, n):
        self.acum[n] = self.dl_meta
        if n not in self.progresso:
            self.progresso.append(n)
        self._ativos.discard(n)
        if len(self.progresso) == len(self.nomes):
            self._fim("CONCLUIDO", "TRANSFERÊNCIA COMPLETA")
            self.eventos.append((f"{n} transferido. TODOS OS DADOS RECUPERADOS.", "vitoria"))
        else:
            self.eventos.append(
                (f"{n} transferido ({len(self.progresso)}/{len(self.nomes)}).", "ok")
            )

    # ---------- modo DEFESA (digitar o código da intrusão a tempo) ----------
    def _agendar(self, agora):
        self._prox_ataque = agora + int(self.p["def_intervalo"] * random.uniform(0.6, 1.4) * NS)

    def _novo_ataque(self, agora):
        cod = "".join(random.choice(ALFABETO_CODIGOS) for _ in range(4))
        self.ataque = {"codigo": cod, "prazo": agora + self.p["def_janela"] * NS}
        self.eventos.append((f"ALERTA! INTRUSÃO DETECTADA. Digite {cod} para bloquear!", "alarme"))

    def _tick_defesa(self, agora):
        janela = self.p["def_janela"] * NS
        if self.ataque:
            if agora >= self.ataque["prazo"]:
                self.ataque = None
                self.integridade -= 1
                if self.integridade <= 0:
                    self._fim("FALHOU", "SERVIDOR COMPROMETIDO")
                    self.eventos.append(
                        ("FALHA! Intrusão concluída. SERVIDOR COMPROMETIDO.", "explosao")
                    )
                    return
                self.eventos.append(
                    (
                        f"FALHA! Intrusão concluída. Integridade: {self.integridade}/{self.integ_max}.",
                        "erro",
                    )
                )
                self._agendar(agora)
        elif agora >= self._prox_ataque and self.fim - agora > janela:
            self._novo_ataque(agora)

    def _bloquear(self, codigo):
        if not self.ataque:
            return "Nenhuma intrusão ativa no momento."
        if codigo == self.ataque["codigo"]:
            self.ataque = None
            self.bloqueios += 1
            self._agendar(self.relogio())
            return f"INTRUSÃO BLOQUEADA ({self.bloqueios})."
        return "Código INCORRETO. A intrusão continua ativa!"

    # ---------- modo CONTROLE (um pendrive por equipe segura o ponto) ----------
    def _tick_controle(self, dt):
        pres = [e for e in EQUIPES if e in self.presentes]
        novo = pres[0] if len(pres) == 1 else ("DISPUTA" if len(pres) == 2 else None)
        if novo != self.dono:
            if novo in EQUIPES:
                self.eventos.append((f"{novo} assumiu o controle do ponto.", "alarme"))
            elif novo == "DISPUTA":
                self.eventos.append(("PONTO EM DISPUTA! Ninguém pontua.", "erro"))
            else:
                self.eventos.append(("Ponto livre.", "beep"))
            self.dono = novo
        if self.dono in EQUIPES:
            self.acum_eq[self.dono] += dt
            if self.acum_eq[self.dono] >= self.ctl_meta:
                self.vencedor = self.dono
                self._fim("CONCLUIDO", f"{self.dono} DOMINOU O PONTO")
                self.eventos.append((f"{self.dono} atingiu a meta e DOMINOU O PONTO!", "vitoria"))

    def _fim_controle_por_tempo(self):
        """Acabou o tempo no modo controle: vence quem acumulou mais tempo com o ponto."""
        v, a = self.acum_eq["VERMELHO"], self.acum_eq["AZUL"]
        if v == a:
            self._fim("CONCLUIDO", "EMPATE")
            self.eventos.append(("Tempo esgotado. EMPATE!", "alarme"))
            return
        self.vencedor = "VERMELHO" if v > a else "AZUL"
        self._fim("CONCLUIDO", f"{self.vencedor} DOMINOU O PONTO")
        self.eventos.append(
            (f"Tempo esgotado. {self.vencedor} controlou o ponto por mais tempo!", "vitoria")
        )

    # ---------- ação manual do organizador (falha na porta USB, etc.) ----------
    def avancar_etapa(self):
        self.verificar_tempo()
        e = self.estado
        if e in ("HACKING", "DECIFRAR"):
            return self._acesso()
        if e == "COLETA":
            return self._coleta(next(n for n in self.nomes if n not in self.progresso))
        if e == "DESARME":
            return self._desarme(self.ordem[len(self.progresso)])
        if e == "DOWNLOAD":
            n = next(n for n in self.nomes if n not in self.progresso)
            self._completar_download(n)
            return f"{n} transferido manualmente."
        if e == "DEFESA" and self.ataque:
            return self._bloquear(self.ataque["codigo"])
        return "Esta etapa não pode ser avançada manualmente."

    # ---------- o que a tela mostra ----------
    def painel(self):
        f, agora = self.fase, self.relogio()
        p = self.p
        if f == "HACKING":
            ordem = (
                ""
                if self.cfg.modo == "hacking"
                else "ORDEM:  " + "  >  ".join("████" for _ in self.nomes)
            )
            return dict(
                ordem=ordem,
                alerta=False,
                info=f"TENTATIVAS: {self.tentativas}/{p['tentativas']}   "
                f"CÓDIGO DE {len(self.cfg.codigo_hack)} CARACTERES",
            )
        if f == "DECIFRAR":
            return dict(
                ordem=f"MENSAGEM:  {self.cifrado}",
                alerta=False,
                info=f"TENTATIVAS: {self.tentativas}/{p['tentativas']}   USE A CHAVE ENCONTRADA NO CAMPO",
            )
        if f == "COLETA":
            return dict(
                ordem="COLETADOS: " + (" ".join(self.progresso) or "nenhum"),
                alerta=False,
                info=f"{len(self.progresso)}/{len(self.nomes)} pendrives",
            )
        if f == "DESARME":
            partes = [(f"[{n}]" if n in self.progresso else n) for n in self.ordem]
            return dict(
                ordem="ORDEM:  " + "  >  ".join(partes),
                alerta=False,
                info=f"ERROS: {self.erros}/{p['erros']}   (cada erro: -{PENALIDADE_NS // NS} s)",
            )
        if f == "DOWNLOAD":
            partes = []
            for n in self.nomes:
                pct = min(100, self.acum[n] * 100 // self.dl_meta)
                partes.append(f"[{n} {pct}%]" if n in self.progresso else f"{n} {pct}%")
            return dict(
                ordem="   ".join(partes),
                alerta=False,
                info=f"ERROS: {self.erros}/{p['erros']}   MANTENHA O PENDRIVE CONECTADO",
            )
        if f == "DEFESA":
            barra = "█" * self.integridade + "░" * (self.integ_max - self.integridade)
            info = f"INTEGRIDADE: {barra} ({self.integridade}/{self.integ_max})   BLOQUEADAS: {self.bloqueios}"
            if self.ataque:
                rest = max(0, self.ataque["prazo"] - agora) / NS
                return dict(
                    ordem=f"INTRUSÃO!  DIGITE: {self.ataque['codigo']}   ({rest:4.1f}s)",
                    alerta=True,
                    info=info,
                )
            return dict(ordem="MONITORANDO A REDE...", alerta=False, info=info)
        if f == "CONTROLE":
            meta = self.ctl_meta / NS
            ordem = (
                f"VERMELHO {self.acum_eq['VERMELHO'] / NS:6.1f}s   |   "
                f"AZUL {self.acum_eq['AZUL'] / NS:6.1f}s   (meta {meta:.0f}s)"
            )
            dono = {"DISPUTA": "PONTO EM DISPUTA", None: "PONTO LIVRE"}.get(
                self.dono, f"PONTO: {self.dono}"
            )
            return dict(ordem=ordem, alerta=self.dono == "DISPUTA", info=dono)
        return dict(ordem="", info="", alerta=False)

    def resumo_admin(self):
        """Solução e dados que SÓ o organizador vê."""
        m = self.cfg.modo
        if m in ("campanha", "hacking"):
            linhas = [f"Código do hacking: {self.cfg.codigo_hack}"]
            if m == "campanha":
                linhas.append(f"Ordem dos pendrives: {' > '.join(self.ordem)}")
        elif m == "decifrar":
            linhas = [
                f"Palavra: {self.cfg.codigo_hack} | Chave: {self.chave} | Cifrada: {self.cifrado}"
            ]
        elif m == "desarme":
            linhas = [f"Ordem dos pendrives: {' > '.join(self.ordem)}"]
        elif m in ("coleta", "download"):
            linhas = [f"Pendrives da missão: {', '.join(self.nomes)}"]
        elif m == "controle":
            linhas = ["Pendrives das equipes: VERMELHO e AZUL"]
        else:
            linhas = ["Sem solução: os códigos das intrusões aparecem na tela."]
        return "\n".join(linhas)
