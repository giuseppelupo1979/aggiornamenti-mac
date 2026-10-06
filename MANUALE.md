# Manuale d'uso

Aggiornamenti è una piccola pagina web che gira solo sul tuo Mac. Controlla tutte le applicazioni installate, ti mostra quali hanno una versione più recente e le aggiorna senza finestre, senza conferme e senza dover aprire le singole app.

## Aprire il programma

Fai doppio clic sull'app **Aggiornamenti** sulla Scrivania (oppure su **Aggiornamenti.command** nella cartella del progetto). Si apre il browser all'indirizzo `http://127.0.0.1:8765` e parte subito un controllo. La prima volta macOS potrebbe chiederti conferma per aprire un file scaricato: clic destro sul file, poi **Apri**.

Se il programma è già attivo, il doppio clic apre solo la pagina. Puoi anche tenerla tra i preferiti del browser.

## Leggere l'elenco

In alto vedi quanti aggiornamenti sono disponibili e quando è stato fatto l'ultimo controllo. Sotto, due gruppi:

- **Applicazioni**: le app che usi ogni giorno.
- **Strumenti da riga di comando**: programmi installati con Homebrew, utili soprattutto a chi sviluppa.

Ogni riga mostra icona, nome, versione installata, versione nuova e da dove arriva l'aggiornamento:

- **Homebrew**: catalogo pubblico di Homebrew.
- **App Store**: aggiornamento ufficiale del Mac App Store.
- **Sito dello sviluppatore**: il canale di aggiornamento interno dell'app (Sparkle).

Due etichette meritano attenzione:

- **versione maggiore**: il primo numero della versione cambia (per esempio da 19 a 27). Spesso significa una nuova licenza a pagamento o cambiamenti importanti, per questo non viene selezionata in automatico.
- **da verificare**: il programma ha abbinato l'app al catalogo solo per nome, senza conferma dell'identificativo. Controlla che sia davvero la stessa app prima di aggiornarla.

## Aggiornare

Al termine del controllo sono già selezionati tutti gli aggiornamenti sicuri. Poi:

- clic su una riga per selezionarla o deselezionarla;
- **Seleziona tutto** per selezionare o togliere tutto in un colpo;
- **Aggiorna** (o **Aggiorna tutto**) per partire.

Gli aggiornamenti vengono eseguiti uno alla volta. Ogni riga passa da *In coda* a *In corso* e poi ad *Aggiornata*. Se un'app è aperta, viene chiusa con garbo, aggiornata e riaperta in background. Puoi chiudere la pagina durante gli aggiornamenti: il lavoro continua e ritrovi lo stato quando la riapri.

Se una riga finisce in **Non riuscito**, cliccaci sopra per leggere il dettaglio.

**Controlla** ripete la ricerca da capo.

## La password di amministratore

Alcuni aggiornamenti richiedono i privilegi di amministratore: tutti quelli del Mac App Store e le app che si installano con un pacchetto `.pkg`. Per farli in silenzio il programma ha bisogno della password del Mac.

In fondo alla pagina apri **Password di amministratore**, scrivi la password e premi **Salva**. Prima viene verificata, poi salvata nel **Portachiavi** di macOS (la stessa cassaforte dove il Mac tiene le password di Safari e delle reti Wi-Fi). Non finisce in nessun file e non esce mai dal Mac. Il pallino verde indica che è impostata. **Rimuovi** la cancella.

Senza password tutto il resto funziona lo stesso: solo gli aggiornamenti che la richiedono finiranno in *Non riuscito*.

## Come funziona, in breve

- Le app installate con Homebrew vengono aggiornate con `brew upgrade`.
- Le app installate a mano ma presenti nel catalogo Homebrew vengono sostituite con la versione del catalogo. Da quel momento sono gestite da Homebrew, che le terrà aggiornate.
- Le app del Mac App Store passano da `mas`.
- Le altre app con aggiornamento Sparkle vengono scaricate dal sito dello sviluppatore. Prima di sostituire la vecchia versione il programma controlla che la firma digitale sia valida e appartenga allo stesso sviluppatore; se non coincide, si ferma.

## Limiti da conoscere

- Le app che si aggiornano da sole con sistemi propri (Microsoft AutoUpdate, Adobe Creative Cloud, Google Chrome) vengono gestite solo se presenti nel catalogo Homebrew.
- Gli aggiornamenti di macOS non sono inclusi: si fanno da Impostazioni di Sistema.
- Il confronto delle versioni è numerico. Se uno sviluppatore numera in modo strano (2.6.4 contro 2.26) può comparire un falso aggiornamento: in quel caso basta deselezionarlo.

## Chiudere il programma

Il server resta attivo in background finché non riavvii il Mac (o sempre, se hai scelto l'avvio automatico con `installa.sh`). Per fermarlo:

```bash
kill $(lsof -tiTCP:8765 -sTCP:LISTEN)
```

Il registro degli eventi è in `~/Library/Logs/AggiornamentiMac.log`.
