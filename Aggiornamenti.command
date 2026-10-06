#!/bin/sh
# Doppio clic: avvia il server (se non è già attivo) e apre la pagina.
DIR="$(cd "$(dirname "$0")" && pwd)"
URL="http://127.0.0.1:8765"
if ! curl -s -o /dev/null "$URL/api/state"; then
  nohup /usr/bin/env python3 "$DIR/server.py" > "$HOME/Library/Logs/AggiornamentiMac.log" 2>&1 &
  for i in 1 2 3 4 5 6 7 8 9 10; do
    curl -s -o /dev/null "$URL/api/state" && break
    sleep 0.5
  done
fi
open "$URL"
