# Aggiornamenti per macOS

Una pagina web locale, sobria, che trova tutte le app del Mac da aggiornare e le aggiorna in silenzio, senza finestre né conferme. Scegli quali aggiornare o aggiornale tutte con un clic.

Gira solo sul tuo computer (`127.0.0.1`), usa soltanto la libreria standard di Python e strumenti già diffusi nel mondo Mac (Homebrew e `mas`).

Il manuale d'uso completo è in [MANUALE.md](MANUALE.md).

## Cosa controlla

| Fonte | Come trova gli aggiornamenti | Come aggiorna |
|---|---|---|
| App installate con Homebrew | `brew outdated --greedy` | `brew upgrade --cask` |
| App installate a mano | confronto con il [catalogo Homebrew](https://formulae.brew.sh) | `brew install --cask --force` (da qui in poi gestite da Homebrew) |
| Mac App Store | `mas outdated` | `mas update` |
| App con Sparkle non presenti nel catalogo | feed di aggiornamento dello sviluppatore | download, verifica della firma, sostituzione |
| Strumenti da riga di comando | `brew outdated` | `brew upgrade --formula` |

Le app aperte vengono chiuse, aggiornate e riaperte in background. Ogni pacchetto mostra una barra di avanzamento con la fase in corso, e le app che non vuoi toccare si possono escludere: finiscono in una sezione separata da cui puoi comunque aggiornarle a mano.

## Requisiti

- macOS 13 o successivo, Apple Silicon o Intel
- [Homebrew](https://brew.sh)
- Python 3 (quello di Homebrew va benissimo)
- [`mas`](https://github.com/mas-cli/mas) per il Mac App Store, accesso all'App Store già effettuato

## Installazione

1. Installa Homebrew, se non c'è già:

   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. Scarica il progetto:

   ```bash
   git clone https://github.com/giuseppelupo1979/aggiornamenti-mac.git ~/aggiornamenti-mac
   ```

3. Prepara l'ambiente (installa `python3` e `mas` se mancano, e chiede se avviare il programma a ogni accesso):

   ```bash
   ~/aggiornamenti-mac/installa.sh
   ```

4. Apri l'app **Aggiornamenti** che lo script ha messo sulla Scrivania (oppure `Aggiornamenti.command`): avvia il server se serve e apre [http://127.0.0.1:8765](http://127.0.0.1:8765).

5. Facoltativo, ma serve per gli aggiornamenti davvero silenziosi dell'App Store e dei pacchetti `.pkg`: in fondo alla pagina inserisci la password di amministratore. Viene verificata e salvata nel Portachiavi di macOS.

## Sicurezza

- Il server ascolta solo su `127.0.0.1` e rifiuta richieste di modifica provenienti da altri siti.
- La password di amministratore sta solo nel Portachiavi (voce `aggiornamenti-mac`); `askpass.sh` la passa a `sudo` quando serve. Non viene mai scritta su disco né mostrata nei processi.
- Le app aggiornate via Sparkle vengono installate solo se la firma del codice è valida e appartiene allo stesso sviluppatore della versione installata.
- Gli aggiornamenti di versione maggiore e gli abbinamenti non verificati non vengono selezionati in automatico.

## File

| File | Ruolo |
|---|---|
| `server.py` | server locale: scansione, aggiornamenti, icone |
| `index.html` | interfaccia |
| `askpass.sh` | fornisce a `sudo` la password dal Portachiavi |
| `Aggiornamenti.command` | avvio con doppio clic |
| `installa.sh` | preparazione dell'ambiente, app sulla Scrivania, avvio automatico |
| `MANUALE.md` | manuale d'uso |

## Disinstallazione

```bash
launchctl bootout gui/$(id -u)/com.aggiornamenti-mac 2>/dev/null
rm -f ~/Library/LaunchAgents/com.aggiornamenti-mac.plist
security delete-generic-password -s aggiornamenti-mac 2>/dev/null
rm -rf ~/Library/Caches/AggiornamentiMac "$HOME/Library/Application Support/AggiornamentiMac"
```

poi cancella la cartella del progetto e l'app `Aggiornamenti` dalla Scrivania.

## Limiti

- Gli aggiornamenti di macOS non sono inclusi.
- Le app con sistemi di aggiornamento propri (Microsoft AutoUpdate, Adobe) sono coperte solo se presenti nel catalogo Homebrew.
- Il confronto delle versioni è numerico: numerazioni insolite possono generare qualche falso positivo, che basta deselezionare.
