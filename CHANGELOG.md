# Changelog

Tutte le modifiche rilevanti al progetto. Le versioni seguono il [versionamento semantico](https://semver.org/lang/it/).

## [1.11.0] - 2026-11-10

### Sicurezza
- **Codice di accesso ai comandi.** Il server accetta comandi solo con un codice casuale salvato in `~/Library/Application Support/AggiornamentiMac/token` (leggibile solo dal tuo utente). Lo ricevono l'app sulla Scrivania, l'icona nella barra dei menu, le notifiche e il comando `aggiornamenti`, che aprono la pagina con il codice nell'indirizzo; la pagina lo conserva e lo toglie subito dalla barra degli indirizzi. Prima bastava conoscere la porta per far partire installazioni, anche con la password di amministratore salvata. Limite dichiarato: un programma che gira già con il tuo utente può leggere il codice, come può leggere la password nel Portachiavi con lo strumento `security`; il codice ferma siti web e programmi che conoscono solo la porta.
- **Firma degli aggiornamenti Sparkle (EdDSA).** Se l'app installata dichiara una chiave pubblica (`SUPublicEDKey`), il file scaricato deve avere una firma `sparkle:edSignature` valida per quella chiave, come pretende Sparkle stesso; altrimenti l'aggiornamento è annullato. Verifica Ed25519 (RFC 8032) scritta con la sola libreria standard, provata sui vettori ufficiali e su un aggiornamento reale di DockDoor (un file alterato di un bit viene rifiutato).

### Aggiunto
- **Icona nella barra dei menu.** `aggiornamenti app` crea sulla Scrivania una vera app (compilata con swiftc, già presente con gli strumenti richiesti da Homebrew) che avvia il server, apre la pagina e resta nella barra dei menu con il numero di aggiornamenti: Apri, Controlla ora, Esci. Parte da sola anche quando il server si avvia all'accesso; si spegne in Controllo automatico. Senza swiftc resta il lanciatore semplice di prima.
- **Novità prima di aggiornare.** Accanto alla versione: le note dello sviluppatore per le app Sparkle (mostrate come testo, senza eseguire nulla), il sito per le app di Homebrew, la scheda dell'App Store, la pagina della formula per gli strumenti da riga di comando.
- **Ripristina la versione precedente.** Prima di aggiornare un'app ne viene conservata una copia per 7 giorni (fino a 2 GB per app, attivo di serie, si spegne in Controllo automatico). Nello Storico, **Ripristina** la rimette al suo posto. Per le app gestite da Homebrew il ripristino vale fino al prossimo aggiornamento: escludila se vuoi restare alla versione vecchia. Le copie scadute si cancellano con la pulizia.

### Corretto
- **Python stabile per chi installa con Homebrew.** La formula dipende ora da `python@3.13` e lo usa per percorso fisso: gli aggiornamenti di Python di Homebrew (nell'ultimo mese il comando `python3` è sparito e poi è passato alla 3.15) non possono più impedire l'avvio.

### Verifica
- 70 test automatici (codice di accesso, firme corrette e manomesse, note, copia e ripristino reali su disco); su GitHub anche la compilazione dell'app per la barra dei menu.
- Prove sul Mac reale: pagina senza codice bloccata e con codice funzionante, link alle novità, app nella barra dei menu che avvia il server. Nessun aggiornamento di terze parti installato durante le prove; il ripristino è provato solo nei test, su un'app finta.

## [1.10.1] - 2026-10-19

### Corretto
- L'app sulla Scrivania poteva fallire con il messaggio generico "Il comando è terminato con uno stato non-zero (127)". Causa probabile, non riprodotta: il comando `aggiornamenti` cercava solo `python3`, che Homebrew non crea più dopo alcuni aggiornamenti di Python (qui dal passaggio di `python@3.14` alla 3.14.8_2): ora usa anche i nomi versionati (`python3.14`, `python3.13`…) e verifica che l'interprete funzioni prima di sceglierlo.
- L'app sulla Scrivania non scarta più gli errori: finiscono nel registro `~/Library/Logs/AggiornamentiMac.log` e l'avviso dice il codice, dove guardare e come avviare il programma dal Terminale. Rigenerala con `aggiornamenti app`.
- Il riavvio dopo l'auto-aggiornamento non fallisce più se l'interprete da cui era partito il server è stato rimosso da un aggiornamento di Python fatto da Homebrew.

## [1.10.0] - 2026-10-11

Porta su macOS le dieci migliorie della versione Windows 0.4.0.

### Aggiunto
- **Verifica dopo l’installazione:** legge versione e build dal bundle dell’app, dalla ricevuta locale Homebrew o da `mas list`. Un comando riuscito senza versione confermata termina con **Da verificare**, non con Aggiornata. Gli installer `.pkg` gestiti direttamente via Sparkle segnalano le richieste di riavvio/uscita dalla sessione dichiarate dal pacchetto, senza eseguirle.
- **Condizioni per gli aggiornamenti automatici:** solo con alimentazione esterna e senza hotspot/reti in modalità Consumo limitato, attive di serie. macOS comunica lo stato della rete tramite Network.framework, senza nuove dipendenze. Se una condizione non è verificabile si rimanda; la pagina mostra motivo e prossimo tentativo. Gli aggiornamenti manuali restano disponibili.
- **Rimanda** per 24 ore o una settimana, **Salta questa versione**, **Riprendi** e sezione separata Rimandate. I rinvii sopravvivono al riavvio e restano distinti dalle esclusioni permanenti.
- **Storico dettagliato** degli ultimi 300 tentativi, filtri per app ed esito, versione rilevata, codice di uscita e log. Esportazione JSON locale con oscuramento dei percorsi utente, email, URL e credenziali riconoscibili.
- **Tema** Come macOS, Chiaro o Scuro, salvato nelle impostazioni; focus da tastiera, selezione parziale, etichette accessibili e rispetto di Riduci movimento.

### Interfaccia
- Accento blu per le azioni, verde per gli esiti riusciti e ambra per le verifiche richieste.
- Pannelli per elenco, storico e impostazioni; versioni e fonti con gerarchia più leggibile.
- Righe selezionate evidenziate e caselle quadrate con angoli arrotondati.
- Intestazione compatta sempre visibile con **Aggiorna N app**; disposizione adattata alle finestre strette.

### Corretto
- Recupero notturno entro cinque ore anche quando la finestra attraversa mezzanotte; nuovi tentativi ogni cinque minuti se mancano le condizioni o la scansione fallisce.
- Lo storico resta aperto durante il cambio dei filtri; il focus segue i comandi dopo il ridisegno.
- Validazione delle impostazioni e rifiuto delle selezioni vecchie o rimandate; rimossa una possibilità di blocco del comando Rimanda dopo una mancata chiusura.
- Cache demo e dati dei test isolati dalle impostazioni personali.

### Verifica
- 54 test automatici con installazioni simulate, prova della demo nel browser e lettura delle versioni reali su macOS. Nessuna app di terze parti aggiornata durante le prove.

## [1.9.1] - 2026-10-10

### Corretto
- La pagina poteva smettere di aprirsi (connessione chiusa, pagina bianca) mentre il programma restava attivo. Succede quando la cartella del programma sta sulla Scrivania, in Documenti o in Download e il server è stato avviato dall'app sulla Scrivania: macOS, per i permessi di privacy, a un certo punto gli negava la lettura di `index.html`, che veniva riletta a ogni apertura. Ora la pagina si legge una volta all'avvio e resta in memoria; se non è leggibile nemmeno all'avvio compare un messaggio che spiega cosa fare. Le installazioni con Homebrew non erano colpite.

## [1.9.0] - 2026-10-09

Porta sul Mac le correzioni e le novità nate con la versione per Windows (0.3.0), dalla revisione indipendente del codice e dai suggerimenti di chi la sta provando.

### Aggiunto
- **Interrompi:** durante un giro di aggiornamenti il pulsante Aggiorna diventa Interrompi. L'installazione in corso finisce (fermarla a metà danneggerebbe l'app), le altre tornano da fare.
- **Forza chiusura / Rimanda:** se un'app aperta non si chiude da sola entro 10 secondi (per esempio perché chiede di salvare un documento), non viene più aggiornata comunque: la riga mostra "Non si chiude da sola" e decidi tu. Forza chiusura chiede conferma.
- **Storico** degli aggiornamenti in fondo alla pagina (ultimi 300, in `storico.json`), con versioni ed esito.
- **Esci** in fondo alla pagina: chiude il programma, ma se un aggiornamento è in corso aspetta che finisca. La pagina rimasta aperta mostra "Aggiornamenti è stato chiuso" invece di dati vecchi, anche quando il server viene fermato in altro modo, e torna normale quando lo riapri. Con avvio all'accesso e controlli spenti il programma funziona solo quando lo apri tu.
- Link **Dettagli** accanto all'esito di ogni riga; Escludi sempre visibile e raggiungibile da tastiera.
- Test automatici (`tests/`, 20 prove con i comandi di sistema simulati) che girano su GitHub Actions a ogni push, più una prova della modalità demo.

### Corretto
- **Falso "tutto aggiornato":** se Homebrew non rispondeva, l'elenco risultava vuoto. Ora il controllo fallito lo dice e la pagina mostra l'ultimo elenco valido; App Store, Aggiornamento Software e aggiornamento del catalogo che non rispondono compaiono come avviso.
- Un errore inatteso durante un aggiornamento poteva lasciare il programma bloccato su "Aggiornamento in corso" fino al riavvio. Ora ogni installazione chiude sempre con un esito.
- Un'app che mostrava una domanda alla chiusura poteva bloccare la richiesta per minuti e far fallire l'intero giro.
- Di notte un'app aperta dopo il controllo iniziale veniva chiusa: ora ogni app si ricontrolla un attimo prima della sua installazione e, se aperta, si rimanda.
- L'aggiornamento notturno recuperava a qualsiasi ora del giorno dopo il risveglio del Mac: ora solo entro 5 ore dall'orario scelto. Se il programma è occupato all'ora prevista la giornata non viene più segnata come fatta.
- Il controllo giornaliero fallito non manda più notifiche e si ripete.
- L'auto-aggiornamento da una copia git installava l'ultimo stato del ramo invece della versione pubblicata: ora installa il tag della Release.
- L'ultima riga dell'output di un comando, spesso proprio il messaggio d'errore, poteva mancare nei Dettagli.
- Impostazioni, esclusioni e storico non si sovrascrivono più a vicenda quando due operazioni scrivono insieme; un file rovinato non blocca il programma.
- Le richieste alla pagina con dati malformati vengono rifiutate con un errore chiaro (limite 64 KB).
- Il messaggio "Tutto aggiornato" ora dice "Nessun aggiornamento" e ricorda le app che il programma non sa controllare.

## [1.8.2] - 2026-10-09

### Corretto
- Aggiornando Aggiornamenti tramite Homebrew la versione precedente restava installata accanto alla nuova (e `brew uninstall` poi chiedeva `--force`). Ora viene rimossa subito dopo l'aggiornamento. Trovato nel test reale dell'auto-aggiornamento da 1.8.0 a 1.8.1.

## [1.8.1] - 2026-10-09

### Migliorato
- Durante l'installazione di una nuova versione di Aggiornamenti il sottotitolo della pagina dice cosa sta succedendo ("Installazione di Aggiornamenti…", poi "Riavvio in corso…") invece del generico "Aggiornamento in corso…".
- `aggiornamenti help` spiega come usare `AGG_PORT`.

## [1.8.0] - 2026-10-09

### Aggiunto
- Avviso di nuove versioni di Aggiornamenti stesso: riquadro in cima alla pagina con link alle novità e pulsante "Installa", più una notifica di macOS dal controllo giornaliero (una sola per versione). Il controllo legge l'ultima Release su GitHub al massimo ogni 6 ore, oppure subito premendo "Controlla".
- Installazione della nuova versione con un clic, adattata a come il programma è stato installato: `brew upgrade` per il tap Homebrew, `git` per una copia clonata (rifiutato se ci sono modifiche locali), archivio della Release per una copia scaricata. Il server si riavvia da solo e la pagina si ricarica sulla nuova versione.
- Variabile `AGG_PORT` per usare una porta diversa dalla 8765.

### Corretto
- Un blocco (deadlock) introdotto durante lo sviluppo di questa funzione, trovato nei test prima della pubblicazione.

## [1.7.0] - 2026-10-08

### Aggiunto
- Installazione con un comando tramite tap Homebrew: `brew install giuseppelupo1979/tap/aggiornamenti`.
- Comando `aggiornamenti` con le azioni `open`, `start`, `stop`, `demo`, `app` e `version`; l'app sulla Scrivania e `Aggiornamenti.command` passano da lì.
- Modalità demo (`aggiornamenti demo`, porta 8766): app di esempio e aggiornamenti simulati, cartelle temporanee, nessuna modifica al sistema.
- Interfaccia e notifiche in inglese o italiano secondo la lingua del Mac (forzabile con `?lang=en` o `?lang=it`).
- README in inglese con GIF e screenshot, `LEGGIMI.md` in italiano, licenza MIT.

### Migliorato
- Un'app aggiornata resta al suo posto nell'elenco con la scritta "Aggiornata" invece di spostarsi in fondo.
- L'avvio all'accesso usa percorsi stabili di Python e del programma, che non cambiano quando Homebrew si aggiorna.
- Funziona anche con il Python 3.9 di sistema di macOS.

### Corretto
- L'avviso degli aggiornamenti di macOS veniva cancellato subito dopo essere stato disegnato e non compariva mai.

### Sicurezza
- Il server risponde solo a richieste indirizzate a `127.0.0.1` o `localhost` (controllo dell'header `Host`), per difendersi dal DNS rebinding.

## [1.6.0] - 2026-10-06

### Aggiunto
- Pulizia automatica al termine di ogni giro di aggiornamenti, manuale o notturno: installer scaricati, vecchie versioni degli strumenti Homebrew, file temporanei e icone non più usate (`brew cleanup --prune=all -s`).
- Pulsante "Libera spazio ora" e indicazione dello spazio liberato nell'ultima pulizia; il resoconto dell'aggiornamento notturno riporta anche lo spazio liberato.
- All'avvio vengono rimossi i file temporanei lasciati da aggiornamenti interrotti.

### Corretto
- Homebrew conservava ogni installer scaricato e le versioni precedenti degli strumenti: sul Mac di prova la prima pulizia ha liberato 6,4 GB.

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
