# Changelog

Tutte le modifiche rilevanti al progetto. Le versioni seguono il [versionamento semantico](https://semver.org/lang/it/).

## [1.5.0] - 2026-10-06

### Aggiunto
- Controllo giornaliero pianificato (di serie alle 9:00) con notifica di macOS; un clic sulla notifica apre la pagina.
- Aggiornamento automatico notturno facoltativo: solo app non escluse, senza versioni maggiori né abbinamenti da verificare, e senza mai chiudere un'app aperta (viene rimandata). Resoconto via notifica e nella pagina.
- Recupero dei controlli saltati quando il Mac dormiva all'ora prevista.
- Opzione "Avvia Aggiornamenti all'accesso" direttamente dalla pagina (LaunchAgent dell'utente).
- Pulsante "Prova una notifica".
- Sezione "Non controllate" con le app senza una fonte di aggiornamento leggibile, il motivo e un link di ricerca.
- Avviso degli aggiornamenti di macOS disponibili, con pulsante per aprire Aggiornamento Software.
- `installa.sh` installa anche `terminal-notifier`.

### Migliorato
- Le app che Homebrew installa con un `.pkg` (Microsoft Office, Teams, OneDrive, TeamViewer, Stream Deck, Logitech) vengono riconosciute tramite il bundle id: 11 aggiornamenti in più trovati sul Mac di prova.
- Confronto con il numero di build quando ha lo stesso formato della versione del catalogo: niente più falsi aggiornamenti per le app Microsoft.
- Le web app di Chrome e le scorciatoie di Google Drive non vengono più considerate app autonome.

### Corretto
- Cambiare un orario già passato, o attivare l'aggiornamento notturno durante il giorno, non fa più partire subito il giro: il primo avviene il giorno dopo.
- Se la porta è già occupata il server esce senza errori, così l'avvio all'accesso non entra in un ciclo di riavvii.

## [1.4.0] - 2026-10-06

### Corretto
- Gli aggiornamenti Sparkle distribuiti come archivio contenente un installer `.pkg` (per esempio NordVPN) ora vengono installati invece di fallire con "Nessuna app trovata nell'archivio".

### Sicurezza
- Un `.pkg` viene installato solo se firmato con certificato Developer ID e dallo stesso sviluppatore dell'app già installata.

## [1.3.0] - 2026-10-06

### Aggiunto
- Link "Escludi" su ogni riga: l'app esce dall'elenco principale, dal conteggio e dalla selezione automatica.
- Sezione separata "Escluse", chiusa di serie, da cui aggiornare comunque un'app a mano o reincluderla.
- Elenco delle esclusioni salvato in `~/Library/Application Support/AggiornamentiMac/esclusi.json`.

## [1.2.0] - 2026-10-06

### Aggiunto
- Barra di avanzamento per ogni pacchetto con la fase in corso: download, installazione, sostituzione della versione precedente, rifinitura.
- Percentuale reale del download: per le app Homebrew misurando il file in cache contro la dimensione dichiarata dal server, per gli strumenti da riga di comando leggendo il manifest della bottle, per Sparkle direttamente.
- Barra generale "N di M" durante un giro di aggiornamenti.

### Migliorato
- Le barre si aggiornano sul posto senza ridisegnare la pagina, così le animazioni restano fluide.

## [1.1.0] - 2026-10-06

### Aggiunto
- App "Aggiornamenti" sulla Scrivania con l'icona di Aggiornamento Software: avvia il server se serve e apre la pagina.
- `installa.sh` può creare l'app sulla Scrivania.

### Corretto
- Il launcher poteva restare bloccato circa due minuti: aggiunto un timeout ai controlli del server.

## [1.0.0] - 2026-10-06

### Aggiunto
- Pagina web locale (`127.0.0.1:8765`) che elenca le app da aggiornare, con selezione singola, "Seleziona tutto" e "Aggiorna tutto".
- Fonti: app Homebrew, app installate a mano confrontate con il catalogo Homebrew, Mac App Store tramite `mas`, canali Sparkle, strumenti da riga di comando.
- Aggiornamenti silenziosi; le app aperte vengono chiuse e riaperte in background.
- Password di amministratore facoltativa, verificata e salvata solo nel Portachiavi, per App Store e pacchetti `.pkg`.
- Etichette "versione maggiore" e "da verificare", non selezionate in automatico.
- Verifica della firma del codice prima di sostituire un'app scaricata via Sparkle.
- Manuale in italiano, README, `installa.sh` con avvio automatico facoltativo.
