# Manuale d'uso

Aggiornamenti è una piccola pagina web che gira solo sul tuo Mac. Controlla tutte le applicazioni installate, ti mostra quali hanno una versione più recente e le aggiorna senza finestre, senza conferme e senza dover aprire le singole app.

## Aprire il programma

Fai doppio clic sull'app **Aggiornamenti** sulla Scrivania, oppure scrivi `aggiornamenti` nel Terminale. Si apre il browser all'indirizzo `http://127.0.0.1:8765` e parte subito un controllo. Se l'app sulla Scrivania non c'è, la crea il comando `aggiornamenti app`. La prima volta macOS potrebbe chiederti conferma per aprirla: clic destro, poi **Apri**.

Se il programma è già attivo, viene aperta solo la pagina. Puoi anche tenerla tra i preferiti del browser.

La pagina è in italiano o in inglese secondo la lingua del Mac. Per provare il programma senza toccare nulla c'è `aggiornamenti demo`: mostra app di esempio e simula gli aggiornamenti, senza modificare il sistema.

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

Gli aggiornamenti vengono eseguiti uno alla volta. In alto compare una barra generale (per esempio *2 di 5 · 40%*); sotto ogni riga una barra mostra la fase in corso:

- **Download**, con i megabyte scaricati e la percentuale reale quando la dimensione del file è nota (barra animata quando non lo è);
- **Installazione**;
- **Sostituzione della versione precedente**;
- **Rifinitura**, poi la riga diventa *Aggiornata*.

Se l'app era aperta vedrai anche *Chiusura* all'inizio e *Riapertura* alla fine. Se un'app è aperta, viene chiusa con garbo, aggiornata e riaperta in background. Puoi chiudere la pagina durante gli aggiornamenti: il lavoro continua e ritrovi lo stato quando la riapri.

Se una riga finisce in **Non riuscito**, cliccaci sopra per leggere il dettaglio.

**Controlla** ripete la ricerca da capo.

## Spazio su disco

Al termine di ogni giro di aggiornamenti, manuale o notturno, il programma cancella tutto ciò che non serve più: gli installer scaricati, le versioni precedenti degli strumenti da riga di comando e i file temporanei. Restano solo il catalogo delle versioni e le icone, una ventina di MB che servono a ogni controllo.

In **Controllo automatico** trovi quanto spazio ha liberato l'ultima pulizia e il pulsante **Libera spazio ora**, utile anche per programmi installati con Homebrew al di fuori di questa pagina.

## Escludere un'app

Passando con il mouse su una riga compare a destra **Escludi**. L'app sparisce dall'elenco principale: non viene più contata, non viene selezionata in automatico e non rientra in **Aggiorna tutto**. Utile per le app che vuoi tenere a una versione precisa, quelle con licenza legata alla versione o i falsi aggiornamenti.

Le app escluse finiscono in fondo alla pagina, nella sezione chiusa **Escluse**. Il titolo dice quante sono e quante hanno un aggiornamento disponibile. Aprila solo quando ti serve: da lì puoi selezionare un'app esclusa e aggiornarla lo stesso con il pulsante **Aggiorna**, oppure riportarla nell'elenco principale con **Includi**.

L'elenco delle esclusioni è salvato in `~/Library/Application Support/AggiornamentiMac/esclusi.json` e resta valido anche dopo il riavvio del Mac.

## Controllo automatico e notifiche

In fondo alla pagina apri **Controllo automatico**. Le opzioni sono tre.

**Controlla ogni giorno alle…** (attiva di serie, alle 9:00): a quell'ora il programma cerca gli aggiornamenti e, se ne trova, ti manda una notifica di macOS con il numero e i primi nomi. Un clic sulla notifica apre la pagina. La prima volta macOS potrebbe chiederti di consentire le notifiche: accetta, altrimenti non le vedrai. Il pulsante **Prova una notifica** serve proprio a controllarlo.

**Aggiorna da solo ogni notte alle…** (spenta di serie): a quell'ora il programma controlla e aggiorna senza chiederti nulla, poi ti lascia una notifica con il resoconto. Per prudenza tocca solo le app non escluse, salta le versioni maggiori e gli abbinamenti da verificare, e non chiude mai un'app aperta: se la stai usando la rimanda alla notte dopo. Sotto le opzioni trovi l'esito dell'ultimo giro automatico.

**Avvia Aggiornamenti all'accesso**: perché i controlli pianificati funzionino il programma deve essere attivo. Con questa opzione parte da solo a ogni accesso al Mac, in silenzio, senza aprire finestre. Finché è spenta, la pagina mostra un avviso in rosso.

Se il Mac dorme all'ora prevista, il controllo parte appena si risveglia. Se imposti un orario già passato oggi, il primo giro sarà domani.

## App non controllate

In fondo all'elenco c'è la sezione chiusa **Non controllate**. Contiene le app per cui il programma non ha trovato una fonte di aggiornamento che sappia leggere, con il motivo:

- *Nessuna fonte di aggiornamento conosciuta*: l'app non è nel catalogo Homebrew e non ha un canale Sparkle;
- *Il catalogo Homebrew non indica il numero di versione*: l'app è nel catalogo, ma senza versione da confrontare;
- *Il sito dello sviluppatore non ha risposto* o *Canale di aggiornamento non sicuro*: il canale esiste ma non è utilizzabile.

Non significa che siano vecchie, solo che nessuno le ha verificate. **Cerca** apre una ricerca sul web per la pagina di download. Le app di Apple e le scorciatoie di Google Drive non compaiono, perché si aggiornano insieme a macOS e a Drive.

## Aggiornamenti di macOS

Se c'è un aggiornamento del sistema, in cima all'elenco compare un riquadro con il nome della versione e il pulsante **Apri Impostazioni**, che porta direttamente alla pagina Aggiornamento Software. Il programma non installa macOS da solo, perché di solito richiede un riavvio.

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
- Gli aggiornamenti di macOS vengono segnalati ma non installati: si fanno da Impostazioni di Sistema.
- Il confronto delle versioni è numerico. Se uno sviluppatore numera in modo strano (2.6.4 contro 2.26) può comparire un falso aggiornamento: in quel caso basta deselezionarlo.

## Chiudere il programma

Il server resta attivo in background finché non riavvii il Mac, oppure sempre se hai attivato l'avvio all'accesso. Per fermarlo:

```bash
aggiornamenti stop
```

Il registro degli eventi è in `~/Library/Logs/AggiornamentiMac.log`.
