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

Durante il giro il pulsante **Aggiorna** diventa **Interrompi**: il programma finisce l'installazione in corso (fermarla a metà lascerebbe l'app danneggiata) e lascia le altre per dopo, di nuovo selezionabili.

Se un'app da aggiornare è aperta, il programma le chiede di chiudersi (vedrai *Chiusura dell'app*), la aggiorna e la riapre in background (*Riapertura dell'app*). Se non si chiude entro qualche secondo, per esempio perché chiede di salvare un documento, **non la forza**: la riga mostra *Non si chiude da sola* con due pulsanti. **Forza chiusura** la chiude d'autorità, dopo una conferma, perché eventuali modifiche non salvate andrebbero perse; **Rimanda** la rimette tra gli aggiornamenti da fare. Puoi anche salvare il lavoro, chiudere l'app tu e premere di nuovo Aggiorna.

Puoi chiudere la pagina durante gli aggiornamenti: il lavoro continua e ritrovi lo stato quando la riapri.

Se una riga finisce in **Non riuscito**, clicca **Dettagli** accanto per leggere il motivo. Ogni aggiornamento, riuscito o no, finisce nello **Storico** in fondo alla pagina, con versione di partenza, versione nuova ed esito.

**Controlla** ripete la ricerca da capo. Se il controllo non riesce (per esempio senza rete o con Homebrew che non risponde), il sottotitolo lo dice e la pagina mostra l'ultimo elenco valido: non scrive mai "nessun aggiornamento" per errore. Se invece non risponde solo una fonte secondaria (App Store, Aggiornamento Software, aggiornamento del catalogo Homebrew), sopra l'elenco compare una riga rossa che dice quale.

## Spazio su disco

Al termine di ogni giro di aggiornamenti, manuale o notturno, il programma cancella tutto ciò che non serve più: gli installer scaricati, le versioni precedenti degli strumenti da riga di comando e i file temporanei. Restano solo il catalogo delle versioni e le icone, una ventina di MB che servono a ogni controllo.

In **Controllo automatico** trovi quanto spazio ha liberato l'ultima pulizia e il pulsante **Libera spazio ora**, utile anche per programmi installati con Homebrew al di fuori di questa pagina.

## Escludere un'app

A destra di ogni riga c'è **Escludi**. L'app sparisce dall'elenco principale: non viene più contata, non viene selezionata in automatico e non rientra in **Aggiorna tutto**. Utile per le app che vuoi tenere a una versione precisa, quelle con licenza legata alla versione o i falsi aggiornamenti.

Le app escluse finiscono in fondo alla pagina, nella sezione chiusa **Escluse**. Il titolo dice quante sono e quante hanno un aggiornamento disponibile. Aprila solo quando ti serve: da lì puoi selezionare un'app esclusa e aggiornarla lo stesso con il pulsante **Aggiorna**, oppure riportarla nell'elenco principale con **Includi**.

L'elenco delle esclusioni è salvato in `~/Library/Application Support/AggiornamentiMac/esclusi.json` e resta valido anche dopo il riavvio del Mac.

## Controllo automatico e notifiche

In fondo alla pagina apri **Controllo automatico**. Le opzioni sono tre.

**Controlla ogni giorno alle…** (attiva di serie, alle 9:00): a quell'ora il programma cerca gli aggiornamenti e, se ne trova, ti manda una notifica di macOS con il numero e i primi nomi. Un clic sulla notifica apre la pagina. La prima volta macOS potrebbe chiederti di consentire le notifiche: accetta, altrimenti non le vedrai. Il pulsante **Prova una notifica** serve proprio a controllarlo.

**Aggiorna da solo ogni notte alle…** (spenta di serie): a quell'ora il programma controlla e aggiorna senza chiederti nulla, poi ti lascia una notifica con il resoconto. Per prudenza tocca solo le app non escluse, salta le versioni maggiori e gli abbinamenti da verificare, e non chiude mai un'app aperta: ogni app viene ricontrollata un attimo prima della sua installazione e, se la stai usando, rimandata alla notte dopo. Se il controllo notturno non riesce, non aggiorna nulla alla cieca. Sotto le opzioni trovi l'esito dell'ultimo giro automatico.

**Avvia Aggiornamenti all'accesso**: perché i controlli pianificati funzionino il programma deve essere attivo. Con questa opzione parte da solo a ogni accesso al Mac, in silenzio, senza aprire finestre. Finché è spenta e un controllo è pianificato, la pagina mostra un avviso in rosso.

Se il Mac dorme all'ora prevista, il controllo giornaliero parte appena si risveglia. L'aggiornamento notturno invece recupera solo entro cinque ore dall'orario scelto (con le 3:00, fino alle 8:00): se il Mac resta spento, si riprova la notte dopo, così non si ritrova a chiudere e aggiornare app a metà giornata. Se il programma è occupato all'ora prevista, la giornata non viene considerata fatta e si riprova poco dopo. Se imposti un orario già passato oggi, il primo giro sarà domani.

**Solo quando lo apri tu.** Spegnendo entrambe le opzioni e l'avvio all'accesso, Aggiornamenti funziona solo quando lo apri. In fondo alla pagina, accanto alla versione, **Esci** lo chiude del tutto: se un aggiornamento è in corso aspetta che finisca, mai a metà. La pagina rimasta aperta mostra *Aggiornamenti è stato chiuso* invece di dati vecchi, e torna normale da sola quando lo riapri dall'app sulla Scrivania o con il comando `aggiornamenti`.

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

## Nuove versioni di Aggiornamenti

Il programma controlla da solo se è uscita una sua nuova versione, al massimo ogni sei ore e ogni volta che premi **Controlla**. Quando c'è, in cima alla pagina compare un riquadro con il numero della versione, il link **Novità** e il pulsante **Installa**; il controllo giornaliero manda anche una notifica, una sola volta per ogni versione.

Premendo **Installa** il programma si aggiorna nel modo in cui l'hai installato: con Homebrew se l'hai preso dal tap, con git se hai clonato il repository, scaricando l'archivio della versione se l'hai scaricato a mano. Poi si riavvia e la pagina si ricarica da sola. Se hai modificato i file di una copia clonata con git, l'aggiornamento automatico si ferma per non perdere le tue modifiche e ti chiede di farlo a mano.

## Chiudere il programma

Il server resta attivo in background finché non riavvii il Mac, oppure sempre se hai attivato l'avvio all'accesso. Per fermarlo:

```bash
aggiornamenti stop
```

Il registro degli eventi è in `~/Library/Logs/AggiornamentiMac.log`.
