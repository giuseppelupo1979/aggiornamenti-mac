// Aggiornamenti: app sulla Scrivania e icona nella barra dei menu.
//
// Avvia il server (comando `aggiornamenti start`), apre la pagina e resta nella barra dei menu con
// il numero di aggiornamenti disponibili. Menu: Apri, Controlla ora, Esci. Costruita da
// `aggiornamenti app` con swiftc (incluso negli strumenti da riga di comando che Homebrew richiede).
import AppKit

let it = (Locale.preferredLanguages.first ?? "en").hasPrefix("it")
func tr(_ a: String, _ b: String) -> String { it ? a : b }

let info = Bundle.main.infoDictionary ?? [:]
let launcher = info["AGGLauncher"] as? String ?? "aggiornamenti"
let logPath = info["AGGLog"] as? String ?? NSHomeDirectory() + "/Library/Logs/AggiornamentiMac.log"
let port = ProcessInfo.processInfo.environment["AGG_PORT"] ?? "8765"
let base = "http://127.0.0.1:\(port)"
let tokenPath = NSHomeDirectory() + "/Library/Application Support/AggiornamentiMac/token"

func token() -> String {
    (try? String(contentsOfFile: tokenPath, encoding: .utf8))?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
}

final class App: NSObject, NSApplicationDelegate, NSMenuDelegate {
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    var state: [String: Any]? = nil
    var timer: Timer?
    let background = CommandLine.arguments.contains("--background")

    func applicationDidFinishLaunching(_ n: Notification) {
        if let b = item.button {
            b.image = NSImage(systemSymbolName: "arrow.triangle.2.circlepath", accessibilityDescription: "Aggiornamenti")
            b.image?.isTemplate = true
            b.imagePosition = .imageLeading
        }
        let menu = NSMenu()
        menu.delegate = self
        item.menu = menu
        startServer(openPage: !background)
        timer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in self?.refresh() }
    }

    // un secondo clic sull'app sulla Scrivania riapre la pagina
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        startServer(openPage: true)
        return false
    }

    func startServer(openPage: Bool) {
        DispatchQueue.global().async {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/bin/sh")
            p.arguments = ["-c", "'\(launcher.replacingOccurrences(of: "'", with: "'\\''"))' start >> '\(logPath)' 2>&1"]
            var code: Int32 = 127
            do { try p.run(); p.waitUntilExit(); code = p.terminationStatus } catch {}
            DispatchQueue.main.async {
                if code != 0 {
                    let a = NSAlert()
                    a.alertStyle = .warning
                    a.messageText = tr("Aggiornamenti non è partito (codice \(code))", "Aggiornamenti did not start (code \(code))")
                    a.informativeText = tr("Dettagli nel registro: \(logPath)\n\nPuoi avviarlo anche dal Terminale con: \(launcher)",
                                           "Details in the log: \(logPath)\n\nYou can also start it from Terminal with: \(launcher)")
                    NSApp.activate(ignoringOtherApps: true)
                    a.runModal()
                    return
                }
                if openPage { self.open() }
                self.refresh()
            }
        }
    }

    func open() {
        if let u = URL(string: "\(base)/#t=\(token())") { NSWorkspace.shared.open(u) }
    }

    func request(_ path: String, post: Bool = false, done: @escaping ([String: Any]?) -> Void) {
        guard let u = URL(string: base + path) else { return done(nil) }
        var r = URLRequest(url: u, timeoutInterval: 5)
        r.setValue(token(), forHTTPHeaderField: "X-Agg-Token")
        if post {
            r.httpMethod = "POST"
            r.httpBody = "{}".data(using: .utf8)
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        URLSession.shared.dataTask(with: r) { data, resp, _ in
            let ok = (resp as? HTTPURLResponse)?.statusCode == 200
            let json = ok ? (data.flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any]) : nil
            DispatchQueue.main.async { done(json) }
        }.resume()
    }

    func refresh() {
        request("/api/state") { s in
            self.state = s
            if let settings = s?["settings"] as? [String: Any], settings["menubar"] as? Bool == false {
                NSApp.terminate(nil)   // icona spenta nelle impostazioni
                return
            }
            let n = s?["pending_count"] as? Int ?? 0
            self.item.button?.title = n > 0 ? " \(n)" : ""
            self.item.button?.appearsDisabled = s == nil
        }
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        func add(_ title: String, _ action: Selector?, enabled: Bool = true) {
            let m = NSMenuItem(title: title, action: action, keyEquivalent: "")
            m.target = self
            m.isEnabled = enabled && action != nil
            menu.addItem(m)
        }
        guard let s = state else {
            add(tr("Aggiornamenti non è attivo", "Aggiornamenti is not running"), nil, enabled: false)
            add(tr("Avvia Aggiornamenti", "Start Aggiornamenti"), #selector(openPage))
            menu.addItem(.separator())
            add(tr("Chiudi l'icona", "Close the icon"), #selector(closeIcon))
            return
        }
        let n = s["pending_count"] as? Int ?? 0
        let busy = (s["running"] as? Bool ?? false) || (s["scanning"] as? Bool ?? false)
        let line = (s["scanning"] as? Bool ?? false) ? tr("Controllo in corso…", "Checking…")
            : (s["running"] as? Bool ?? false) ? tr("Aggiornamento in corso…", "Updating…")
            : n == 0 ? tr("Nessun aggiornamento", "No updates")
            : n == 1 ? tr("1 aggiornamento disponibile", "1 update available")
            : tr("\(n) aggiornamenti disponibili", "\(n) updates available")
        add(line, nil, enabled: false)
        menu.addItem(.separator())
        add(tr("Apri Aggiornamenti", "Open Aggiornamenti"), #selector(openPage))
        add(tr("Controlla ora", "Check now"), busy ? nil : #selector(checkNow))
        menu.addItem(.separator())
        add(tr("Esci da Aggiornamenti", "Quit Aggiornamenti"), #selector(quitAll))
    }

    @objc func openPage() { startServer(openPage: true) }
    @objc func checkNow() { request("/api/scan", post: true) { _ in self.refresh() } }
    @objc func closeIcon() { NSApp.terminate(nil) }

    // come Esci nella pagina: se un aggiornamento è in corso il server esce appena finisce
    @objc func quitAll() { request("/api/quit", post: true) { _ in NSApp.terminate(nil) } }
}

let app = NSApplication.shared
let delegate = App()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
