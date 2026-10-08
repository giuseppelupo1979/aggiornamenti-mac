#!/bin/sh
# Doppio clic: avvia il server (se non è già attivo) e apre la pagina.
exec "$(cd "$(dirname "$0")" && pwd)/aggiornamenti" open
