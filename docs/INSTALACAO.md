# Instalação no notebook (Debian 13 sem interface gráfica)

O resultado final: o notebook liga, faz o login sozinho e abre direto o **Terminal de Missão**,
sem área de trabalho, sem barra de tarefas e sem tela de login. Visual 100% militar.

## 1. Instalar o Debian 13 (trixie) sem desktop

1. Grave o ISO *netinst* amd64 num pendrive e dê boot por ele (**Install**, não "Graphical install", se preferir texto).
2. Siga o instalador normalmente (idioma, teclado, rede, usuário comum e senha).
3. Na tela **Seleção de software** (*Software selection*):
   - **desmarque** "Debian desktop environment", GNOME, KDE, Xfce e todos os outros ambientes;
   - **mantenha** "standard system utilities";
   - marque "SSH server" se quiser administrar o notebook pela rede (opcional).
4. Instale o GRUB no disco e reinicie. Você cairá numa tela preta de login em texto.

## 2. Instalar o Terminal de Missão

Entre com o usuário comum (ex.: `missao`) e rode:

```bash
su -c "apt-get update && apt-get install -y git sudo"   # só se ainda não tiver o git/sudo
git clone https://github.com/Strikedio/terminal-missao.git
cd terminal-missao
sudo ./instalacao/instalar_kiosk.sh missao
sudo reboot
```

> Se o `sudo` não estiver configurado, use `su -` e rode o script como root:
> `./instalacao/instalar_kiosk.sh missao`.

Sem internet no notebook? Copie a pasta do projeto por pendrive. O script só precisa de rede para baixar os pacotes.

### O que o script faz

| Item | Efeito |
|------|--------|
| Pacotes | servidor X mínimo, openbox, python3-tk, som (alsa), automontagem de pendrives (udisks2 + udiskie) |
| Programa | copiado para `~/terminal-missao` |
| Login automático | no console 1, sem pedir senha |
| Início | `startx` abre o Terminal de Missão em tela cheia; se o programa travar ele reinicia sozinho |
| Permissões | regra polkit para o seu usuário montar pendrives sem senha |
| Energia | fechar a tampa não suspende; tela nunca apaga |
| GRUB | espera 2 s e boot silencioso (`--sem-grub` para não mexer; backup em `/etc/default/grub.bak-missao`) |
| Som | volume em 90% e sem mudo |

## 3. Manutenção

| Preciso de... | Faça |
|---------------|------|
| Abrir um console de texto | `Ctrl+Alt+F2` (login com usuário e senha) |
| Sair do programa | F12 → senha → **SAIR DO PROGRAMA** (volta ao console 1) |
| Desligar | F12 → senha → **DESLIGAR NOTEBOOK** (2 cliques) |
| Atualizar o programa | `cd terminal-missao && git pull && sudo ./instalacao/instalar_kiosk.sh missao --sem-grub` |
| Desativar o quiosque temporariamente | `touch ~/.sem-quiosque` e reinicie (apague o arquivo para reativar) |
| Desfazer tudo | `sudo ./instalacao/instalar_kiosk.sh missao --remover` |

## 4. Problemas comuns

- **Tela preta e volta ao login:** entre no console (`Ctrl+Alt+F2`) e rode `startx ~/.quiosque-sessao.sh` para ver o erro.
- **Pendrive não é detectado:** confirme que ele aparece em `/media/<usuario>/` (`ls /media/*`). O arquivo `pendrive.key` deve estar na raiz do pendrive.
- **Sem som:** rode `alsamixer`, tecle `M` nos canais mudos e depois `sudo alsactl store`. Em notebooks com placa de som incomum pode faltar firmware (`sudo apt install firmware-sof-signed`, exige o repositório *non-free-firmware*).
- **Teclado com layout errado:** `sudo dpkg-reconfigure keyboard-configuration`.
- **Wi-Fi:** não é necessário para jogar. Se precisar de rede para atualizar, use cabo.
