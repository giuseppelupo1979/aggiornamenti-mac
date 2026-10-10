"""Test del server con i comandi del Mac simulati: nessuna app viene chiusa o aggiornata davvero.

Avvio: python3 -m unittest discover -s tests -v
"""
import copy
import datetime as dt
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = tempfile.TemporaryDirectory(prefix="agg-test-")
os.environ["AGG_DATA_DIR"] = SANDBOX.name   # impostazioni, cache e registro finiscono nella cartella di prova
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
             patch.object(s, "run", side_effect=run), patch.object(s, "verify_install", return_value=("done", "1.1")):
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
        with patch.object(s, "automatic_block_reason", return_value=None), patch.object(s, "running_app", return_value=True), patch.object(s, "quit_app") as quit_, \
             patch.object(s, "run_stream") as run:
            s.update_one(ITEM, mode="auto")
        quit_.assert_not_called()
        run.assert_not_called()
        self.assertEqual(s.state["jobs"][ITEM["id"]]["status"], "postponed")

    def test_force_mode_kills_only_on_request(self):
        with patch.object(s, "running_app", return_value=True), patch.object(s, "force_quit", return_value=True) as force, \
             patch.object(s, "quit_app") as quit_, patch.object(s, "run_stream", return_value=(0, "")), \
             patch.object(s, "remote_size", return_value=None), patch.object(s, "run", return_value=(0, "")), patch.object(s, "verify_install", return_value=("done", "1.1")):
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


class Page(Base):
    def test_page_is_served_from_memory_when_disk_read_is_denied(self):
        s._page["html"] = None
        first = s.load_page()
        with patch("builtins.open", side_effect=PermissionError("Operation not permitted")):
            self.assertEqual(s.load_page(), first)   # come quando macOS nega la Scrivania dopo l'avvio
        self.assertIn(b"Aggiornamenti", first)

    def test_unreadable_page_gives_clear_error(self):
        s._page["html"] = None
        with patch("builtins.open", side_effect=PermissionError("Operation not permitted")):
            self.assertIsNone(s.load_page())
        s._page["html"] = None


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


class Snooze(Base):
    def test_timed_snooze_expires(self):
        with patch.object(s.time, "time", return_value=1000):
            s.snooze_item(ITEM, "day")
        self.assertIsNotNone(s.active_snooze(ITEM, now=87399))
        self.assertIsNone(s.active_snooze(ITEM, now=87400))

    def test_skip_only_requested_version(self):
        s.snooze_item(ITEM, "version")
        self.assertIsNotNone(s.active_snooze(ITEM))
        self.assertIsNone(s.active_snooze(dict(ITEM, latest="1.2")))
        self.assertEqual(s.visible_pending(), [])

    def test_resume_keeps_exclusion(self):
        s.save_excluded({ITEM["key"]: {"name": "App"}})
        s.snooze_item(ITEM, "week")
        s.snooze_item(ITEM, "resume")
        self.assertIsNone(s.active_snooze(ITEM))
        self.assertIn(ITEM["key"], s.load_excluded())

    def test_queue_cannot_install_snoozed_app(self):
        s.snooze_item(ITEM, "week")
        with patch.object(s, "update_one") as up, patch.object(s, "cleanup"):
            s.do_updates({ITEM["id"]})
        up.assert_not_called()


class Conditions(Base):
    def test_battery_or_unknown_power_blocks_automatic_updates(self):
        for ac, reason in ((False, "battery"), (None, "power_unknown")):
            with patch.object(s, "on_ac_power", return_value=ac):
                self.assertEqual(s.automatic_block_reason(), reason)

    def test_metered_and_unknown_network_block_automatic_updates(self):
        with patch.object(s, "on_ac_power", return_value=True):
            for cost in ("metered", "unknown", "offline", "unrestricted"):
                with patch.object(s, "network_cost", return_value=cost):
                    self.assertEqual(s.automatic_block_reason(), None if cost == "unrestricted" else cost)

    def test_opt_out_does_not_probe_system(self):
        with patch.object(s, "on_ac_power") as power, patch.object(s, "network_cost") as cost:
            self.assertIsNone(s.automatic_block_reason(dict(s.DEFAULT_SETTINGS, only_ac=False, avoid_metered=False)))
        power.assert_not_called()
        cost.assert_not_called()

    def test_blocked_auto_does_not_scan_or_consume_day(self):
        with patch.object(s, "automatic_block_reason", return_value="battery"), patch.object(s, "start_scan_sync") as scan:
            self.assertFalse(s.auto_update())
        scan.assert_not_called()
        self.assertEqual(s.state["auto_wait"], "battery")
        self.assertIsNone(s.load_settings()["last_auto_day"])

    def test_condition_rechecked_before_install(self):
        with patch.object(s, "automatic_block_reason", return_value="metered"), patch.object(s, "run_stream") as run:
            s.update_one(ITEM, "auto")
        run.assert_not_called()
        self.assertEqual(s.state["jobs"][ITEM["id"]]["status"], "deferred")

    def test_night_window_crosses_midnight(self):
        now = dt.datetime(2026, 10, 11, 1, 0)
        self.assertTrue(s.due("23:00", None, now, 5))
        self.assertFalse(s.due("23:00", "2026-10-10", now, 5))
        self.assertFalse(s.due("23:00", None, now.replace(hour=4), 5))

    def test_next_attempt_respects_window_and_completed_night(self):
        now = dt.datetime(2026, 10, 11, 6, 0)
        settings = dict(s.DEFAULT_SETTINGS, auto_update=True)
        self.assertEqual(s.next_auto_attempt(settings, now), (now + dt.timedelta(seconds=30)).timestamp())
        settings["last_auto_day"] = "2026-10-11"
        self.assertEqual(s.next_auto_attempt(settings, now), dt.datetime(2026, 10, 12, 3).timestamp())


class Diagnostics(Base):
    def test_export_redacts_personal_data_without_changing_versions(self):
        raw = r'C:\Users\Alice\file.log alice@example.org https://example.org/?token=secret token=abc'
        s.add_history({"name": "App", "from": "1.2.3.4", "log": raw})
        report = s.diagnostic_report()
        encoded = json.dumps(report)
        for private in ("Alice", "alice@example.org", "example.org", "secret", "abc"):
            self.assertNotIn(private, encoded)
        self.assertEqual(report["history"][0]["from"], "1.2.3.4")

    def test_settings_changes_preserve_snoozes(self):
        s.snooze_item(ITEM, "week")
        s.update_settings(lambda x: x.update(theme="light"))
        self.assertIsNotNone(s.active_snooze(ITEM))

    def test_defaults_are_not_mutated_by_snoozing(self):
        s.snooze_item(ITEM, "week")
        Path(s.SETTINGS_FILE).unlink()
        self.assertEqual(s.load_settings()["snoozed"], {})

    def test_redaction_covers_bearer_and_quoted_password(self):
        self.assertNotIn("private-token", s.redact("Authorization: Bearer private-token"))
        self.assertNotIn("private phrase", s.redact('password="a private phrase"'))


class NewApi(Base):
    def post(self, path, body):
        handler = object.__new__(s.Handler)
        raw = json.dumps(body).encode()
        handler.headers = {"Host": f"{s.HOST}:{s.PORT}", "Content-Length": str(len(raw))}
        handler.path = path
        handler.rfile = io.BytesIO(raw)
        replies = []
        handler.send = lambda code, payload: replies.append((code, payload))
        handler.snapshot = lambda: {"ok": True}
        handler.do_POST()
        return replies[-1]

    def test_settings_reject_invalid_types(self):
        for body in ({"only_ac": "false"}, {"avoid_metered": 0}, {"theme": "no"}, {"auto_time": "25:00"}):
            with self.subTest(body=body):
                self.assertEqual(self.post("/api/settings", body)[0], 400)

    def test_settings_saved_without_losing_snooze(self):
        s.snooze_item(ITEM, "version")
        self.assertEqual(self.post("/api/settings", {"only_ac": False, "theme": "dark"})[0], 200)
        self.assertFalse(s.load_settings()["only_ac"])
        self.assertEqual(s.load_settings()["theme"], "dark")
        self.assertIsNotNone(s.active_snooze(ITEM))

    def test_snooze_validated_and_persisted(self):
        self.assertEqual(self.post("/api/snooze", {"id": ITEM["id"], "choice": "week"})[0], 200)
        self.assertIsNotNone(s.active_snooze(ITEM))
        self.assertEqual(self.post("/api/snooze", {"id": ITEM["id"], "choice": "forever"})[0], 400)
        self.assertEqual(self.post("/api/snooze", {"id": "missing", "choice": "day"})[0], 404)

    def test_stale_selection_cannot_install_snoozed_app(self):
        s.snooze_item(ITEM, "day")
        self.assertEqual(self.post("/api/update", {"ids": [ITEM["id"]]})[0], 409)
        self.assertFalse(s.state["running"])

    def test_cannot_snooze_during_install(self):
        s.state["running"] = True
        self.assertEqual(self.post("/api/snooze", {"id": ITEM["id"], "choice": "day"})[0], 409)
        self.assertIsNone(s.active_snooze(ITEM))




class MacVerification(Base):
    def test_bundle_version_and_build_are_read_from_disk(self):
        info = {"CFBundleIdentifier": ITEM["bundle_id"], "CFBundleShortVersionString": "1.1", "CFBundleVersion": "123"}
        with patch.object(s, "read_info", return_value=info), patch.object(s, "run") as run:
            for expected in ("1.1", "123", "1.1,123"):
                self.assertEqual(s.installed_version(dict(ITEM, latest=expected)), expected)
        run.assert_not_called()

    def test_missing_or_different_bundle_never_falls_back_to_receipt(self):
        with patch.object(s, "run") as run:
            for info in (None, {"CFBundleIdentifier": "another.app", "CFBundleShortVersionString": "1.1"}):
                with patch.object(s, "read_info", return_value=info):
                    self.assertIsNone(s.installed_version(ITEM))
        run.assert_not_called()

    def test_formula_uses_linked_keg_not_catalog_or_unused_new_version(self):
        data = {"formulae": [{"name": "app", "linked_keg": "1.0", "versions": {"stable": "1.1"},
                              "installed": [{"version": "1.0"}, {"version": "1.1"}]}]}
        with patch.object(s, "run", return_value=(0, json.dumps(data))):
            self.assertEqual(s.installed_version(dict(ITEM, kind="formula", path=None)), "1.0")

    def test_cask_receipt_not_catalog_version(self):
        with patch.object(s, "run", return_value=(0, '{"casks":[{"token":"app","version":"1.1","installed":"1.0"}]}')):
            self.assertEqual(s.installed_version(dict(ITEM, kind="cask", path=None)), "1.0")

    def test_mas_exact_id_only(self):
        with patch.object(s, "run", return_value=(0, '1234 App (1.1)\n123 Other (1.0)')):
            self.assertEqual(s.installed_version(dict(ITEM, kind="mas", token="123")), "1.0")
            self.assertIsNone(s.installed_version(dict(ITEM, kind="mas", token="12")))

    def test_successful_command_with_old_version_needs_verification(self):
        with patch.object(s, "running_app", return_value=False), patch.object(s, "run_stream", return_value=(0, "")), \
             patch.object(s, "remote_size", return_value=None), patch.object(s, "cask_by_token", return_value={}), \
             patch.object(s, "installed_version", return_value="1.0"), patch.object(s.time, "sleep"):
            s.update_one(ITEM)
        self.assertEqual(s.state["jobs"][ITEM["id"]]["status"], "unverified")
        self.assertFalse(s.state["items"][0].get("updated"))
        history = s.load_history()[-1]
        self.assertEqual((history["observed"], history["exit_code"]), ("1.0", 0))

    def test_version_verified_and_log_redacted_in_history(self):
        def install(cmd, log):
            log('/Users/Alice/Downloads/app alice@example.org Authorization: Bearer secret')
            return 0, ""
        with patch.object(s, "running_app", return_value=False), patch.object(s, "run_stream", side_effect=install), \
             patch.object(s, "remote_size", return_value=None), patch.object(s, "cask_by_token", return_value={}), \
             patch.object(s, "installed_version", return_value="1.1"):
            s.update_one(ITEM)
        history = s.load_history()[-1]
        self.assertEqual(history["result"], "done")
        self.assertNotIn("Alice", history["log"])
        self.assertNotIn("secret", history["log"])

    def test_failed_command_is_not_made_successful_by_version(self):
        with patch.object(s, "running_app", return_value=False), patch.object(s, "run_stream", return_value=(1, "")), \
             patch.object(s, "remote_size", return_value=None), patch.object(s, "cask_by_token", return_value={}), \
             patch.object(s, "installed_version") as check:
            s.update_one(ITEM)
        check.assert_not_called()
        self.assertEqual(s.load_history()[-1]["result"], "error")

    def test_version_normalization_does_not_match_suffixes(self):
        self.assertTrue(s.version_matches("1.1.0", "1.1"))
        for a, b in (("1.10", "1.1"), ("1.1-beta", "1.1"), ("Unknown", "Unknown"), (None, "1")):
            self.assertFalse(s.version_matches(a, b))

    def test_restart_metadata_only_applies_after_success(self):
        for code in (0, 1):
            s.state["jobs"][ITEM["id"]] = {"status": "running"}
            with patch.object(s, "has_password", return_value=True), patch.object(s, "run", side_effect=[
                (0, "Developer ID Installer: Test (TEAM123)"), (0, "RequireRestart"), (code, "result")]):
                self.assertEqual(s.install_pkg("/tmp/test.pkg", "TEAM123", ITEM["id"], lambda x: None), code == 0)
            self.assertEqual(s.state["jobs"][ITEM["id"]].get("restart_action"), "RequireRestart" if code == 0 else None)

    def test_sparkle_restart_is_distinct_from_verified_success(self):
        def install(item, log):
            s.state["jobs"][item["id"]].update(restart_action="RequireRestart", exit_code=0)
            return True
        with patch.object(s, "running_app", return_value=False), patch.object(s, "install_sparkle", side_effect=install), \
             patch.object(s, "installed_version", return_value="1.1"):
            s.update_one(dict(ITEM, kind="sparkle"))
        self.assertEqual(s.load_history()[-1]["result"], "restart")
        self.assertFalse(s.state["items"][0].get("updated"))

    def test_power_source_desktop_battery_ups_and_unknown(self):
        for text, expected in (("Now drawing from 'AC Power'", True), ("Now drawing from 'Battery Power'", False),
                               ("Now drawing from 'UPS Power'", False), ("", None)):
            with patch.object(s, "run", return_value=(0, text)):
                self.assertIs(s.on_ac_power(), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
