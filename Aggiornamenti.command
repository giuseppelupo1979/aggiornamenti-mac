#!/bin/sh
# Doppio clic: avvia il server (se non è già attivo) e apre la pagina.
DIR="$(cd "$(dirname "$0")" && pwd)"
URL="http://127.0.0.1:8765"
up() { curl -s --max-time 2 -o /dev/null "$URL/api/state"; }
if ! up; then
  nohup /usr/bin/env PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" python3 "$DIR/server.py" \
    < /dev/null >> "$HOME/Library/Logs/AggiornamentiMac.log" 2>&1 &
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    up && break
    sleep 0.5
  done
fi
open "$URL"
