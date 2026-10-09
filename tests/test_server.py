"""Test del server con i comandi del Mac simulati: nessuna app viene chiusa o aggiornata davvero.

Avvio: python3 -m unittest discover -s tests -v
"""
import copy
import datetime as dt
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = tempfile.TemporaryDirectory(prefix="agg-test-")
os.environ["HOME"] = SANDBOX.name   # impostazioni, cache e registro finiscono nella cartella di prova
os.environ["AGG_LANG"] = "it"
sys.path.insert(0, str(ROOT))
import server as s  # noqa: E402

INITIAL = copy.deepcopy(s.state)
ITEM = dict(id="adopt:app", key="cask:app", kind="adopt", token="app", name="App", installed="1.0",
            latest="1.1", source="homebrew", path="/Applications/App.app", bundle_id="com.example.app")
OUTDATED = '{"formulae": [], "casks": [{"name": "app", "installed_versions": ["1.0"], "current_version": "1.1"}]}'


class Base(unittest.TestCase):
    def setUp(self):
        s.state.clear()
        s.state.update(copy.deepcopy(INITIAL))
        s.state["items"] = [dict(ITEM)]
        s.state["jobs"][ITEM["id"]] = dict(status="running", log="", phase=None, pct=None)
        for p in (s.SETTINGS_FILE, s.EXCLUDED_FILE, s.HISTORY_FILE):
            Path(p).unlink(missing_ok=True)


def fake_run(answers):
    """run() simulato: la prima parola chiave trovata nel comando decide la risposta."""
    def run(cmd, timeout=0, env=None):
        line = " ".join(map(str, cmd))
        for key, answer in answers.items():
            if key in line:
                return answer
        return 0, ""
    return run


class Scan(Base):
    def scan(self, answers):
        s.state["scanning"] = True
        with patch.object(s, "run", side_effect=fake_run(answers)), patch.object(s, "check_self_update"), \
             patch.object(s, "scan_apps", return_value=([], [])), patch.object(s, "attach_paths", side_effect=lambda x: x):
            s.do_scan()

    def test_failed_brew_is_an_error_and_keeps_last_list(self):
        self.scan({"list --cask": (1, "Error: no network"), "softwareupdate": (0, "")})
        self.assertIn("no network", s.state["scan_error"])
        self.assertTrue(s.state["stale"])
        self.assertEqual(s.state["items"][0]["id"], ITEM["id"])   # ultimo elenco valido conservato
        self.assertFalse(s.state["scanning"])

    def test_unreadable_outdated_is_an_error_not_an_empty_list(self):
        self.scan({"outdated": (1, "Error: something broke"), "softwareupdate": (0, "")})
        self.assertTrue(s.state["stale"])
        self.assertEqual(len(s.state["items"]), 1)

    def test_silent_sources_become_warnings(self):
        with patch.object(s.os.path, "exists", return_value=True):
            self.scan({"update --quiet": (1, "offline"), "outdated --json": (0, OUTDATED),
                       "mas outdated": (1, "Error"), "softwareupdate": (1, "Error")})
        self.assertIsNone(s.state["scan_error"])
        self.assertEqual(s.state["scan_warnings"], ["brew_update", "mas", "softwareupdate"])
        self.assertEqual([i["id"] for i in s.state["items"]], ["cask:app"])

    def test_missing_catalog_is_an_error(self):
        with patch.object(s, "cask_catalog", return_value={}):
            with self.assertRaises(s.ScanError):
                s.scan_apps(set())


class Queue(Base):
    def test_unexpected_error_never_leaves_program_busy(self):
        s.state["running"] = True
        with patch.object(s, "running_app", side_effect=subprocess.TimeoutExpired("osascript", 15)), \
             patch.object(s, "cleanup"):
            s.do_updates({ITEM["id"]})
        self.assertFalse(s.state["running"])
        self.assertEqual(s.state["jobs"][ITEM["id"]]["status"], "error")
        self.assertEqual(s.load_history()[-1]["result"], "error")

    def test_reopen_failure_keeps_successful_update(self):
        def run(cmd, timeout=0, env=None):
            if cmd[0] == "open":
                raise OSError("open failed")
            return 0, ""
        with patch.object(s, "running_app", return_value=True), patch.object(s, "quit_app", return_value="closed"), \
             patch.object(s, "run_stream", return_value=(0, "")), patch.object(s, "remote_size", return_value=None), \
             patch.object(s, "run", side_effect=run):
            s.update_one(ITEM)
        self.assertEqual(s.state["jobs"][ITEM["id"]]["status"], "done")
        self.assertTrue(s.state["items"][0]["updated"])

    def test_stop_finishes_current_and_skips_rest(self):
        second = dict(ITEM, id="adopt:other", key="cask:other", token="other", name="Other")
        s.state["items"].append(second)
        s.state["running"] = True

        def fake_update(item, mode):
            s.state["stop"] = True   # "Interrompi" premuto durante la prima installazione
            s.state["jobs"][item["id"]]["status"] = "done"
        with patch.object(s, "update_one", side_effect=fake_update) as up, patch.object(s, "cleanup"):
            s.do_updates({ITEM["id"], second["id"]})
        self.assertEqual(up.call_count, 1)
        self.assertEqual(len(s.state["jobs"]), 1)   # l'altra torna tra quelle da fare
        self.assertFalse(s.state["running"])

    def test_output_without_final_newline_is_kept(self):
        lines = []
        rc, out = s.run_stream([sys.executable, "-c", "import sys; sys.stdout.write('important error')"], lines.append)
        self.assertEqual((rc, out, lines), (0, "important error", ["important error"]))


class Closing(Base):
    def test_app_that_does_not_quit_is_never_killed(self):
        with patch.object(s, "run", return_value=(0, "")), patch.object(s, "running_app", return_value=True), \
             patch.object(s.time, "sleep"), patch.object(s.os, "kill") as kill:
            self.assertEqual(s.quit_app("com.example.app"), "open")
        kill.assert_not_called()

    def test_quit_dialog_timeout_is_not_an_error(self):
        with patch.object(s, "run", side_effect=[subprocess.TimeoutExpired("osascript", 20)] + [(0, "false")] * 5):
            self.assertEqual(s.quit_app("com.example.app"), "closed")

    def test_unclosed_app_becomes_blocked_for_user_choice(self):
        with patch.object(s, "running_app", return_value=True), patch.object(s, "quit_app", return_value="open"), \
             patch.object(s, "run_stream") as run, patch.object(s, "run") as other:
            s.update_one(ITEM)
        run.assert_not_called()
        self.assertFalse(any(c.args[0][0] == "open" for c in other.call_args_list))   # niente riapertura
        self.assertEqual(s.state["jobs"][ITEM["id"]]["status"], "blocked")

    def test_auto_mode_postpones_open_app(self):
        with patch.object(s, "running_app", return_value=True), patch.object(s, "quit_app") as quit_, \
             patch.object(s, "run_stream") as run:
            s.update_one(ITEM, mode="auto")
        quit_.assert_not_called()
        run.assert_not_called()
        self.assertEqual(s.state["jobs"][ITEM["id"]]["status"], "postponed")

    def test_force_mode_kills_only_on_request(self):
        with patch.object(s, "running_app", return_value=True), patch.object(s, "force_quit", return_value=True) as force, \
             patch.object(s, "quit_app") as quit_, patch.object(s, "run_stream", return_value=(0, "")), \
             patch.object(s, "remote_size", return_value=None), patch.object(s, "run", return_value=(0, "")):
            s.update_one(ITEM, mode="force")
        force.assert_called_once()
        quit_.assert_not_called()
        self.assertEqual(s.state["jobs"][ITEM["id"]]["status"], "done")

    def test_app_pids_matches_only_that_app(self):
        ps = ("  10 /Applications/App.app/Contents/MacOS/App\n"
              "  11 /Applications/App Helper.app/Contents/MacOS/Helper\n"
              "  12 /Applications/App.app/Contents/Frameworks/x.app/Contents/MacOS/x\n")
        with patch.object(s, "run", return_value=(0, ps)), patch.object(s.os.path, "realpath", side_effect=lambda p: p):
            self.assertEqual(s.app_pids("/Applications/App.app"), [10])


class Schedule(Base):
    def test_nightly_update_not_due_at_noon(self):
        self.assertFalse(s.due("03:00", "2026-10-08", dt.datetime(2026, 10, 9, 12, 0), s.NIGHT_WINDOW_HOURS))
        self.assertTrue(s.due("03:00", "2026-10-08", dt.datetime(2026, 10, 9, 6, 30), s.NIGHT_WINDOW_HOURS))
        self.assertTrue(s.due("09:00", "2026-10-08", dt.datetime(2026, 10, 9, 18, 0)))   # il controllo recupera

    def test_busy_program_does_not_consume_the_night(self):
        s.update_settings(lambda st: st.update(auto_update=True, auto_time="03:00"))
        night = dt.datetime(2026, 10, 9, 3, 5)
        with patch.object(s, "auto_update", return_value=False), \
             patch.object(s.dt, "datetime", wraps=dt.datetime) as fake_dt, \
             patch.object(s.time, "sleep", side_effect=[None, KeyboardInterrupt]):
            fake_dt.now.return_value = night
            with self.assertRaises(KeyboardInterrupt):
                s.scheduler()
        self.assertIsNone(s.load_settings()["last_auto_day"])

    def test_failed_scan_sends_no_notification(self):
        s.state["stale"] = True
        with patch.object(s, "start_scan_sync", return_value=True), patch.object(s, "notify") as notify:
            self.assertFalse(s.scheduled_check())
        notify.assert_not_called()


class SelfUpdate(Base):
    def test_git_installs_the_release_tag_not_the_branch(self):
        s.state["self"]["latest"] = "9.9.9"
        calls = []

        def run(cmd, timeout=0, env=None):
            calls.append(cmd)
            return (0, "main") if "rev-parse" in cmd else (0, "")
        with patch.object(s, "install_method", return_value="git"), patch.object(s, "run", side_effect=run), \
             patch.object(s, "restart_server"):
            s.do_self_update()
        self.assertIn(["git", "-C", s.ROOT, "merge", "--ff-only", "v9.9.9"], calls)


class Api(Base):
    def test_quit_during_update_waits(self):
        s.state["running"] = True
        with patch.object(s.threading, "Timer") as timer:
            self.assertFalse(s.request_quit())
        timer.assert_not_called()
        self.assertTrue(s.state["quit_after"])
        self.assertFalse(s.state["quitting"])

    def test_corrupt_settings_fall_back_to_defaults(self):
        Path(s.SETTINGS_FILE).write_text("[1, 2]")
        self.assertEqual(s.load_settings()["check_time"], s.DEFAULT_SETTINGS["check_time"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
