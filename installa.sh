#!/bin/bash
# Installazione manuale (senza Homebrew tap): prepara l'ambiente e crea l'app sulla Scrivania.
# Manual install (without the Homebrew tap): sets up dependencies and the Desktop app.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew non è installato / Homebrew is not installed:"
  echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 1
fi

command -v mas >/dev/null 2>&1 || brew install mas
command -v terminal-notifier >/dev/null 2>&1 || brew install terminal-notifier
chmod +x "$DIR/aggiornamenti" "$DIR/server.py" "$DIR/askpass.sh" "$DIR/Aggiornamenti.command"

read -r -p "Creare l'app sulla Scrivania? / Create the Desktop app? [S/n|Y/n] " ans
if [[ ! "$ans" =~ ^[nN] ]]; then
  "$DIR/aggiornamenti" app >/dev/null && echo "OK: ~/Desktop/Aggiornamenti.app"
fi

"$DIR/aggiornamenti" open
echo "Pronto / Ready: http://127.0.0.1:8765"
echo "Avvio all'accesso e controllo automatico si attivano dalla pagina."
echo "Start at login and automatic checks are set from the page."
