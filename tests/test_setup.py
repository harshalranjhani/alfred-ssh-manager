import base64
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alfred_ssh.models import HostEntry
from alfred_ssh.setup import ENSURE_KEY, install_script, perform, setup_output, test_command, validate_public_key

PUBLIC = 'ssh-ed25519 ' + base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20' + bytes(range(32))).decode()


class SetupTests(unittest.TestCase):
    def test_install_preserves_existing_entries_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temp:
            ssh = Path(temp) / '.ssh'
            ssh.mkdir()
            authorized = ssh / 'authorized_keys'
            authorized.write_text('existing-key-without-newline')
            for _ in range(2):
                subprocess.run(['sh', '-c', install_script(PUBLIC)], env={**os.environ, 'HOME': temp}, check=True, capture_output=True)
            self.assertEqual(authorized.read_text(), 'existing-key-without-newline\n' + PUBLIC + '\n')
            self.assertEqual(authorized.stat().st_mode & 0o777, 0o600)
            self.assertEqual(ssh.stat().st_mode & 0o777, 0o700)
            restricted = 'restrict ' + PUBLIC + ' comment\n'
            authorized.write_text(restricted)
            subprocess.run(['sh', '-c', install_script(PUBLIC)], env={**os.environ, 'HOME': temp}, check=True, capture_output=True)
            self.assertEqual(authorized.read_text(), restricted)

    def test_invalid_public_keys_rejected_before_shell_execution(self):
        for key in ['', PUBLIC + '\n' + PUBLIC, 'ssh-rsa AAA', 'ssh-ed25519 $(touch /tmp/no)', 'ssh-ed25519 YQ==']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                install_script(key)
        self.assertEqual(validate_public_key(PUBLIC + ' $(touch /tmp/no)'), PUBLIC)

    def test_existing_key_is_preserved_and_incomplete_pair_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            ssh = Path(temp) / '.ssh'
            ssh.mkdir()
            key = ssh / 'id_ed25519'
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
            before = key.read_bytes()
            env = {**os.environ, 'HOME': temp}
            subprocess.run(['sh', '-c', ENSURE_KEY], env=env, check=True, capture_output=True)
            self.assertEqual(key.read_bytes(), before)
            key.with_suffix('.pub').unlink()
            result = subprocess.run(['sh', '-c', ENSURE_KEY], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(key.read_bytes(), before)
            self.assertIn(b'no files were overwritten', result.stderr)

    def test_menu_resolves_aliases_and_quotes_commands(self):
        entries = [HostEntry(name='build', target='deploy@builder', source='alias'),
                   HostEntry(name='prod', target='deploy@app', source='alias')]
        runner = Path('/workflow with spaces/setup_action.py')
        result = setup_output(entries, [], 'build > prod', runner)['items'][0]
        self.assertEqual(shlex.split(result['arg']), ['/usr/bin/python3', str(runner), 'install', 'deploy@app', 'deploy@builder'])
        local = setup_output(entries, [], 'prod', runner)['items'][0]
        self.assertEqual(shlex.split(local['mods']['cmd']['arg'])[-3:], ['test', 'deploy@app', ''])
        for query in ['-bad > prod', 'build > prod > extra']:
            self.assertFalse(setup_output(entries, [], query, runner)['items'][0]['valid'])
        hostile = "host;$(touch-pwned)"
        result = setup_output([], [], hostile, runner)['items'][0]
        self.assertEqual(shlex.split(result['arg'])[-2], hostile)

    @patch('alfred_ssh.setup.run')
    def test_remote_flow_transfers_public_key_and_tests_on_source(self, run):
        run.side_effect = [None, subprocess.CompletedProcess([], 0, PUBLIC), None,
                           subprocess.CompletedProcess([], 0, 'hostname app.example\nuser deploy\nport 2222\n'), None]
        perform('install', 'prod', 'builder')
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[1][-1], 'cat "$HOME/.ssh/id_ed25519.pub"')
        self.assertIn(PUBLIC, commands[2][-1])
        self.assertIn('app.example', commands[-1][-1])
        self.assertIn('-p 2222', commands[-1][-1])
        self.assertIn('ControlPath=none', commands[-1][-1])
        self.assertIn('PreferredAuthentications=publickey', commands[-1][-1])

    @patch('alfred_ssh.setup.run')
    def test_failed_generation_never_installs(self, run):
        run.side_effect = subprocess.CalledProcessError(1, 'ssh')
        with self.assertRaises(subprocess.CalledProcessError):
            perform('install', 'prod', 'builder')
        self.assertEqual(run.call_count, 1)

    def test_test_command_rejects_options_and_disables_password_fallback(self):
        with self.assertRaises(ValueError):
            test_command('-oProxyCommand=bad')
        command = test_command('prod')
        self.assertIn('PasswordAuthentication=no', command)
        self.assertIn('KbdInteractiveAuthentication=no', command)
        self.assertIn('ControlPath=none', command)


if __name__ == '__main__':
    unittest.main()
