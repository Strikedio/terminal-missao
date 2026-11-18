#!/usr/bin/env bash
# Terminal de Missão - instalação do modo quiosque (sem ambiente de desktop).
#
# Uso, como root, num Debian 13 instalado SEM desktop:
#   sudo ./instalacao/instalar_kiosk.sh [usuario] [--sem-grub]
#   sudo ./instalacao/instalar_kiosk.sh [usuario] --remover
#
# O que faz:
#   1. instala o mínimo necessário (servidor X, openbox, python3-tk, som e automontagem de pendrives);
#   2. copia o programa para ~/terminal-missao do usuário;
#   3. liga o login automático no console 1 e inicia direto o Terminal de Missão (sem tela de login);
#   4. impede a suspensão ao fechar a tampa e deixa a inicialização silenciosa (opção --sem-grub desliga).
set -euo pipefail

RAIZ="${RAIZ:-}"         # prefixo para testes (ex.: /tmp/teste); vazio = sistema real
SIMULAR="${SIMULAR:-0}"  # 1 = não instala pacotes nem chama systemctl/update-grub
MARCA_INI="# >>> terminal-missao >>>"
MARCA_FIM="# <<< terminal-missao <<<"

erro() { echo "ERRO: $*" >&2; exit 1; }
info() { echo -e "\033[1;32m==>\033[0m $*"; }
rodar() { if [ "$SIMULAR" = 1 ]; then echo "[simulado] $*"; else "$@"; fi; }
limpar_bloco() { if [ -f "$1" ]; then sed -i "/$MARCA_INI/,/$MARCA_FIM/d" "$1"; fi; }

USUARIO=""
SEM_GRUB=0
REMOVER=0
for arg in "$@"; do
    case "$arg" in
        --sem-grub) SEM_GRUB=1 ;;
        --remover) REMOVER=1 ;;
        -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
        -*) erro "opção desconhecida: $arg" ;;
        *) USUARIO="$arg" ;;
    esac
done

if [ "$(id -u)" -ne 0 ] && [ "$SIMULAR" != 1 ]; then
    erro "execute como root: sudo $0 [usuario]"
fi
USUARIO="${USUARIO:-${SUDO_USER:-}}"
if [ -z "$USUARIO" ] || [ "$USUARIO" = root ]; then
    erro "informe o usuário comum (não o root): sudo $0 meu_usuario"
fi
getent passwd "$USUARIO" > /dev/null || erro "o usuário '$USUARIO' não existe."

GRUPO="$(id -gn "$USUARIO")"
HOME_U="${HOME_USUARIO:-$(getent passwd "$USUARIO" | cut -d: -f6)}"
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="$HOME_U/terminal-missao"

remover() {
    info "Removendo o modo quiosque do usuário $USUARIO"
    rm -f "$RAIZ/etc/systemd/system/getty@tty1.service.d/autologin.conf"
    rmdir "$RAIZ/etc/systemd/system/getty@tty1.service.d" 2> /dev/null || true
    rm -f "$RAIZ/etc/systemd/logind.conf.d/terminal-missao.conf"
    rm -f "$RAIZ/etc/polkit-1/rules.d/50-terminal-missao.rules"
    limpar_bloco "$HOME_U/.bash_profile"
    rm -f "$HOME_U/.quiosque-sessao.sh"
    rodar systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target
    rodar systemctl daemon-reload
    info "Pronto. O programa em $DESTINO foi mantido. Reinicie para voltar ao login normal."
}

instalar_pacotes() {
    info "Instalando pacotes (precisa de internet)"
    rodar apt-get update
    rodar apt-get install -y --no-install-recommends \
        xserver-xorg-core xserver-xorg-input-libinput xinit x11-xserver-utils openbox \
        python3 python3-tk fonts-dejavu-core alsa-utils \
        udisks2 udiskie dbus libpam-systemd polkitd
    # esconde o cursor do mouse quando parado (opcional)
    rodar apt-get install -y --no-install-recommends unclutter-xfixes \
        || rodar apt-get install -y --no-install-recommends unclutter \
        || info "Aviso: não foi possível instalar o 'unclutter' (o cursor ficará sempre visível)."
}

copiar_projeto() {
    if [ "$PROJ" = "$DESTINO" ]; then
        info "O programa já está em $DESTINO; nada a copiar."
        return
    fi
    info "Copiando o programa para $DESTINO"
    install -d -o "$USUARIO" -g "$GRUPO" "$DESTINO"
    for arq in "$PROJ"/*.py "$PROJ"/README.md; do
        [ -f "$arq" ] || continue
        install -m 644 -o "$USUARIO" -g "$GRUPO" "$arq" "$DESTINO/"
    done
}

escrever_sessao() {
    info "Criando a sessão gráfica mínima"
    cat > "$HOME_U/.quiosque-sessao.sh" <<'SESSAO'
#!/bin/sh
# Sessão gráfica mínima do Terminal de Missão (gerada por instalar_kiosk.sh).
# Refaz a chamada dentro de um barramento D-Bus próprio (necessário para a automontagem).
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ] && command -v dbus-run-session > /dev/null 2>&1; then
    exec dbus-run-session -- "$0" "$@"
fi
cd "$HOME/terminal-missao" || exit 1
xset s off
xset s noblank
xset -dpms
openbox > /dev/null 2>&1 &
udiskie -a -N -T > /dev/null 2>&1 &
if command -v unclutter > /dev/null 2>&1; then
    ( unclutter --timeout 3 || unclutter -idle 3 ) > /dev/null 2>&1 &
fi
# Se o programa cair (código diferente de 0) ele reinicia sozinho.
# "SAIR DO PROGRAMA" no painel (código 0) encerra a sessão e deixa o console livre.
while true; do
    python3 terminal.py
    [ "$?" -eq 0 ] && break
    sleep 1
done
SESSAO
    chown "$USUARIO:$GRUPO" "$HOME_U/.quiosque-sessao.sh"
    chmod 755 "$HOME_U/.quiosque-sessao.sh"
}

escrever_perfil() {
    info "Configurando o início automático no console 1"
    if [ ! -f "$HOME_U/.bash_profile" ]; then
        # o bash deixa de ler ~/.profile quando existe ~/.bash_profile; mantém o comportamento padrão
        printf '%s\n' '[ -f "$HOME/.profile" ] && . "$HOME/.profile"' > "$HOME_U/.bash_profile"
    fi
    limpar_bloco "$HOME_U/.bash_profile"
    cat >> "$HOME_U/.bash_profile" <<PERFIL
$MARCA_INI
# Inicia o Terminal de Missão sozinho no console 1 (crie ~/.sem-quiosque para desativar).
if [ -z "\${DISPLAY:-}" ] && [ "\$(tty)" = "/dev/tty1" ] && [ ! -f "\$HOME/.sem-quiosque" ]; then
    printf '\033[1;32m\n  TERMINAL DE MISSAO\n  Iniciando sistemas...\033[0m\n\n'
    sleep 1
    startx "\$HOME/.quiosque-sessao.sh"
    printf '\nTerminal de missao encerrado.\nPara reiniciar: sudo reboot   Para desligar: sudo poweroff\n'
fi
$MARCA_FIM
PERFIL
    chown "$USUARIO:$GRUPO" "$HOME_U/.bash_profile"
}

configurar_autologin() {
    info "Ligando o login automático para $USUARIO"
    local pasta="$RAIZ/etc/systemd/system/getty@tty1.service.d"
    mkdir -p "$pasta"
    cat > "$pasta/autologin.conf" <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USUARIO --noclear %I \$TERM
EOF
    rodar systemctl daemon-reload
}

configurar_polkit() {
    info "Liberando a montagem de pendrives para $USUARIO"
    local pasta="$RAIZ/etc/polkit-1/rules.d"
    mkdir -p "$pasta"
    cat > "$pasta/50-terminal-missao.rules" <<EOF
polkit.addRule(function(action, subject) {
    if (subject.user == "$USUARIO" && action.id.indexOf("org.freedesktop.udisks2.") == 0) {
        return polkit.Result.YES;
    }
});
EOF
}

configurar_energia() {
    info "Desativando a suspensão (tampa fechada, inatividade)"
    mkdir -p "$RAIZ/etc/systemd/logind.conf.d"
    cat > "$RAIZ/etc/systemd/logind.conf.d/terminal-missao.conf" <<EOF
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
EOF
    rodar systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
}

ajustar_som() {
    rodar amixer -q sset Master 90% unmute || true
    rodar alsactl store || true
}

configurar_grub() {
    local arq="$RAIZ/etc/default/grub"
    if [ ! -f "$arq" ]; then
        info "GRUB não encontrado; pulando a inicialização silenciosa."
        return
    fi
    info "Deixando a inicialização silenciosa (backup em $arq.bak-missao)"
    [ -f "$arq.bak-missao" ] || cp "$arq" "$arq.bak-missao"
    sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=2/' "$arq"
    sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet loglevel=3"/' "$arq"
    rodar update-grub
}

if [ "$REMOVER" = 1 ]; then
    remover
    exit 0
fi

info "Instalando o modo quiosque para o usuário '$USUARIO'"
instalar_pacotes
copiar_projeto
escrever_sessao
escrever_perfil
configurar_autologin
configurar_polkit
configurar_energia
ajustar_som
if [ "$SEM_GRUB" != 1 ]; then
    configurar_grub
fi
info "Pronto! Reinicie com: sudo reboot"
