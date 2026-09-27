import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from alfred_ssh.aliases import alias_entries, load_aliases, parse_add_spec, remove_alias, save_alias
from alfred_ssh.config import Settings
from alfred_ssh.discovery import discover
from alfred_ssh.history import record
from alfred_ssh.hosts_file import discover_hosts_file
from alfred_ssh.known_hosts import discover_known_hosts
from alfred_ssh.search import search_output
from alfred_ssh.ssh_config import discover_ssh_config

ROOT = Path(__file__).resolve().parent.parent


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.ssh = self.root / ".ssh"
        self.ssh.mkdir()
        self.data = self.root / "data"
        self.settings = Settings(
            ssh_config=self.ssh / "config", custom_hosts=self.ssh / "etc_hosts",
            etc_hosts=self.root / "system_hosts", known_hosts=self.ssh / "known_hosts",
            data_dir=self.data,
        )

    def test_ssh_config_includes_literals_and_avoids_cycles(self):
        config_dir = self.ssh / "config.d"
        config_dir.mkdir()
        (self.ssh / "config").write_text(
            "HOST foo # comment\nHost bar baz\n HostName bar.example.com\nInclude config.d/*.conf\nHost *.internal foo-?? !bad *\n", encoding="utf-8")
        (config_dir / "a.conf").write_text("Include ../config\nHost nested\n User deploy\n", encoding="utf-8")
        names = [entry.name for entry in discover_ssh_config(self.settings.ssh_config)]
        self.assertEqual(names, ["foo", "bar", "baz", "nested"])

    def test_hosts_and_known_hosts(self):
        self.settings.custom_hosts.write_text("10.0.0.5 nas nas.home # home\nfd00::1 v6box\ninvalid bad\n", encoding="utf-8")
        self.settings.known_hosts.write_text("github.com,10.0.0.9 ssh-ed25519 AAA\n|1|hash|salt ssh-ed25519 BBB\n@cert-authority git.example.com ssh-ed25519 CCC\n", encoding="utf-8")
        self.assertEqual([e.name for e in discover_hosts_file(self.settings.custom_hosts, "customhosts")], ["nas", "nas.home", "v6box"])
        self.assertEqual([e.name for e in discover_known_hosts(self.settings.known_hosts)], ["github.com", "10.0.0.9", "git.example.com"])

    def test_alias_discovery_search_and_history(self):
        self.settings.ssh_config.write_text("Host production-api\n HostName api.example.com\n User deploy\n", encoding="utf-8")
        self.settings.custom_hosts.write_text("10.0.0.5 nas nas.home\n", encoding="utf-8")
        alias_path = self.data / "aliases.json"
        name, details = parse_add_spec('home=nas.home --fav --tag home --description "My NAS"')
        save_alias(alias_path, name, details)
        self.assertEqual(alias_entries(alias_path)[0].target, "nas.home")
        record(self.data / "history.json", "nas.home")
        entries, errors = discover(self.settings)
        self.assertFalse(errors)
        self.assertEqual([entry.name for entry in entries if entry.name == "nas"], ["nas"])
        item = search_output(entries, errors, "home", self.settings)["items"][0]
        self.assertEqual(item["uid"], "alias:home")
        self.assertEqual(item["arg"], "nas.home")
        self.assertEqual(item["mods"]["alt"]["variables"]["ssh_action"], "sftp")
        self.assertEqual(item["mods"]["ctrl"]["variables"]["ssh_action"], "inspect")
        self.assertEqual(search_output(entries, errors, ":recent", self.settings)["items"][0]["title"], "★ home")
        self.assertTrue(remove_alias(alias_path, "home"))
        self.assertEqual(load_aliases(alias_path), {})

    def test_bad_aliases_do_not_hide_good_sources(self):
        self.settings.ssh_config.write_text("Host good\n", encoding="utf-8")
        self.data.mkdir()
        (self.data / "aliases.json").write_text("{broken", encoding="utf-8")
        entries, errors = discover(self.settings)
        self.assertEqual([entry.name for entry in entries], ["good"])
        self.assertTrue(any("aliases.json" in error for error in errors))

    def test_direct_connection_appears_in_recent_history(self):
        record(self.data / "history.json", "oneoff.example.com")
        entries, errors = discover(self.settings)
        result = search_output(entries, errors, ":recent", self.settings)["items"]
        self.assertEqual(result[0]["uid"], "history:oneoff.example.com")

    def test_alias_cycles_are_rejected(self):
        path = self.data / "aliases.json"
        save_alias(path, "a", {"target": "b"})
        with self.assertRaises(ValueError):
            save_alias(path, "b", {"target": "a"})


class WorkflowTests(unittest.TestCase):
    def test_workflow_graph_and_package(self):
        subprocess.run([sys.executable, str(ROOT / "tools" / "build.py")], check=True, capture_output=True, text=True)
        workflow = plistlib.loads((ROOT / "workflow" / "info.plist").read_bytes())
        types = [obj["type"] for obj in workflow["objects"]]
        self.assertEqual(types.count("alfred.workflow.input.scriptfilter"), 3)
        self.assertEqual(types.count("alfred.workflow.action.terminalcommand"), 2)
        self.assertIn("alfred.workflow.userinterface.text", types)
        self.assertEqual(workflow["bundleid"], "com.harshal.alfred-ssh-manager")
        object_ids = {obj["uid"] for obj in workflow["objects"]}
        for source, destinations in workflow["connections"].items():
            self.assertIn(source, object_ids)
            for destination in destinations:
                self.assertIn(destination["destinationuid"], object_ids)
        with ZipFile(ROOT / "dist" / "Alfred-SSH-Manager.alfredworkflow") as archive:
            self.assertTrue({"info.plist", "icon.png", "scripts/ssh_search.py", "src/alfred_ssh/discovery.py"}.issubset(archive.namelist()))
            with tempfile.TemporaryDirectory() as temp:
                archive.extractall(temp)
                env = {**os.environ, "SSH_CONFIG": str(Path(temp) / "missing_config"),
                       "CUSTOM_HOSTS": str(Path(temp) / "missing_hosts"),
                       "ETC_HOSTS": str(Path(temp) / "missing_system_hosts"),
                       "KNOWN_HOSTS": str(Path(temp) / "missing_known_hosts"),
                       "alfred_workflow_data": str(Path(temp) / "data")}
                result = subprocess.run([sys.executable, str(Path(temp) / "scripts" / "ssh_search.py"), ":help"],
                                        env=env, capture_output=True, text=True, check=True)
                self.assertEqual(json.loads(result.stdout)["items"][0]["title"], "SSH Manager")

    def test_action_quotes_target_and_records_usage(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {**os.environ, "alfred_workflow_data": temp, "ssh_action": "ssh"}
            output = subprocess.run([sys.executable, str(ROOT / "scripts" / "action.py"), "host;touch-pwned"],
                                    env=env, capture_output=True, text=True, check=True)
            self.assertEqual(output.stdout.strip(), "'host;touch-pwned'")
            self.assertEqual(json.loads((Path(temp) / "history.json").read_text())["host;touch-pwned"]["usage_count"], 1)


if __name__ == "__main__":
    unittest.main()
