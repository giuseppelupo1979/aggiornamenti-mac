#!/bin/sh
# Fornisce a sudo la password di amministratore salvata nel Portachiavi.
exec /usr/bin/security find-generic-password -s aggiornamenti-mac -w
