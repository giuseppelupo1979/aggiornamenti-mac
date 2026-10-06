#!/bin/bash
# Prepara l'ambiente per Aggiornamenti e, a richiesta, lo avvia a ogni accesso.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.aggiornamenti-mac"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew non è installato. Installalo con:"
  echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  echo "poi rilancia questo script."
  exit 1
fi

command -v python3 >/dev/null 2>&1 || brew install python
command -v mas >/dev/null 2>&1 || brew install mas

chmod +x "$DIR/server.py" "$DIR/askpass.sh" "$DIR/Aggiornamenti.command"

read -r -p "Avviare Aggiornamenti automaticamente a ogni accesso? [s/N] " ans
if [[ "$ans" =~ ^[sS] ]]; then
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$(command -v python3)</string><string>$DIR/server.py</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/AggiornamentiMac.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/AggiornamentiMac.log</string>
</dict>
</plist>
PL
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  echo "Avvio automatico attivo. Pagina: http://127.0.0.1:8765"
fi

echo "Pronto. Doppio clic su Aggiornamenti.command per aprire la pagina."
