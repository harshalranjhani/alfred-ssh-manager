#!/usr/bin/env python3
"""Generate Alfred's workflow graph and package the distributable."""
import plistlib
import shutil
import struct
import uuid
import zlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "workflow"
STAGE = ROOT / "build" / "Alfred-SSH-Manager"
DIST = ROOT / "dist" / "Alfred-SSH-Manager.alfredworkflow"
NAMESPACE = uuid.UUID("8c04ef98-5f33-4b1a-b972-7f7355d36753")


def uid(name):
    return str(uuid.uuid5(NAMESPACE, name)).upper()


def script_filter(name, keyword, script, title, subtitle):
    return {"type": "alfred.workflow.input.scriptfilter", "uid": uid(name), "version": 3,
            "config": {"alfredfiltersresults": False, "alfredfiltersresultsmatchmode": 0,
                       "argumenttreatemptyqueryasnil": False, "argumenttrimmode": 0,
                       "argumenttype": 1, "escaping": 0, "keyword": keyword,
                       "queuedelaycustom": 0, "queuedelayimmediatelyinitially": True,
                       "queuedelaymode": 0, "queuemode": 1,
                       "runningsubtext": "Loading SSH hosts…", "script": script,
                       "scriptargtype": 1, "scriptfile": "", "subtext": subtitle,
                       "title": title, "type": 0, "withspace": True}}


def run_script(name, script):
    return {"type": "alfred.workflow.action.script", "uid": uid(name), "version": 2,
            "config": {"concurrently": False, "escaping": 0, "script": script,
                       "scriptargtype": 1, "scriptfile": "", "type": 0}}


def keyword(name, word, title, subtitle):
    return {"type": "alfred.workflow.input.keyword", "uid": uid(name), "version": 1,
            "config": {"argumenttype": 2, "keyword": word, "text": title,
                       "subtext": subtitle, "withspace": False}}


def connection(destination, output=None):
    result = {"destinationuid": uid(destination), "modifiers": 0, "modifiersubtext": "", "vitoclose": False}
    if output:
        result["sourceoutputuid"] = uid(output)
    return result


def config_field(variable, label, default, description):
    if isinstance(default, bool):
        return {"type": "checkbox", "variable": variable, "label": label, "description": description,
                "config": {"default": default, "required": False, "text": ""}}
    return {"type": "textfield", "variable": variable, "label": label, "description": description,
            "config": {"default": default, "placeholder": default, "required": False, "trim": True}}


def make_plist():
    objects = [
        script_filter("search", "ssh", '/usr/bin/python3 scripts/ssh_search.py "$1"', "SSH Manager", "Search SSH destinations, aliases, and recent sessions"),
        script_filter("alias_add", "ssha", '/usr/bin/python3 scripts/alias_add.py "$1"', "Create SSH alias", "name=target [--fav] [--tag tag] [--description text]"),
        script_filter("alias_remove", "sshrm", '/usr/bin/python3 scripts/alias_remove.py "$1"', "Remove SSH alias", "Find an Alfred alias to remove"),
        keyword("edit_config", "sshconf", "Edit SSH config", "Open ~/.ssh/config in your default editor"),
        keyword("edit_hosts", "sshhosts", "Edit custom SSH hosts", "Open ~/.ssh/etc_hosts in your default editor"),
        run_script("action", '/usr/bin/python3 scripts/action.py "$1"'),
        run_script("save_alias", '/usr/bin/python3 scripts/alias_mutate.py add "$1"'),
        run_script("delete_alias", '/usr/bin/python3 scripts/alias_mutate.py remove "$1"'),
        run_script("open_config", '/usr/bin/python3 scripts/edit_shortcut.py config'),
        run_script("open_hosts", '/usr/bin/python3 scripts/edit_shortcut.py hosts'),
        {"type": "alfred.workflow.utility.conditional", "uid": uid("route"), "version": 1,
         "config": {"conditions": [
             {"inputstring": "{var:ssh_action}", "matchcasesensitive": False, "matchmode": 0,
              "matchstring": action, "outputlabel": label, "uid": uid("route_" + action)}
             for action, label in [("ssh", "SSH"), ("sftp", "SFTP"), ("copy", "Copy"), ("inspect", "Inspect"), ("edit", "Edit")]
             ], "elselabel": "Other", "hideelse": True}},
        {"type": "alfred.workflow.action.terminalcommand", "uid": uid("terminal_ssh"), "version": 1,
         "config": {"escaping": 0, "script": "ssh {query}"}},
        {"type": "alfred.workflow.action.terminalcommand", "uid": uid("terminal_sftp"), "version": 1,
         "config": {"escaping": 0, "script": "sftp {query}"}},
        {"type": "alfred.workflow.output.clipboard", "uid": uid("clipboard"), "version": 3,
         "config": {"autopaste": False, "clipboardtext": "{query}", "ignoredynamicplaceholders": False, "transient": False}},
        {"type": "alfred.workflow.userinterface.text", "uid": uid("inspect_view"), "version": 1,
         "config": {"behaviour": 2, "fontmode": 0, "fontsizing": 0, "footertext": "Resolved by OpenSSH (ssh -G)",
                    "inputfile": "", "inputtype": 0, "loadingtext": "Resolving SSH configuration…", "outputmode": 0,
                    "scriptinput": 0, "spellchecking": 0, "stackview": False}},
        {"type": "alfred.workflow.output.notification", "uid": uid("copy_notification"), "version": 1,
         "config": {"lastpathcomponent": False, "onlyshowifquerypopulated": True, "text": "{query}", "title": "SSH command copied"}},
        {"type": "alfred.workflow.output.notification", "uid": uid("edit_notification"), "version": 1,
         "config": {"lastpathcomponent": False, "onlyshowifquerypopulated": True, "text": "{query}", "title": "SSH Manager"}},
        {"type": "alfred.workflow.output.notification", "uid": uid("alias_notification"), "version": 1,
         "config": {"lastpathcomponent": False, "onlyshowifquerypopulated": True, "text": "{query}", "title": "SSH Manager"}},
    ]
    connections = {
        uid("search"): [connection("action")],
        uid("action"): [connection("route")],
        uid("route"): [connection("terminal_ssh", "route_ssh"), connection("terminal_sftp", "route_sftp"),
                       connection("clipboard", "route_copy"), connection("inspect_view", "route_inspect"),
                       connection("edit_notification", "route_edit")],
        uid("clipboard"): [connection("copy_notification")],
        uid("alias_add"): [connection("save_alias")],
        uid("alias_remove"): [connection("delete_alias")],
        uid("save_alias"): [connection("alias_notification")],
        uid("delete_alias"): [connection("alias_notification")],
        uid("edit_config"): [connection("open_config")],
        uid("edit_hosts"): [connection("open_hosts")],
        uid("open_config"): [connection("edit_notification")],
        uid("open_hosts"): [connection("edit_notification")],
    }
    positions = {"search": (40, 100), "action": (260, 100), "route": (480, 100),
                 "terminal_ssh": (700, 0), "terminal_sftp": (700, 110), "clipboard": (700, 220),
                 "copy_notification": (920, 220), "inspect_view": (700, 330), "edit_notification": (700, 440),
                 "alias_add": (40, 610), "save_alias": (260, 610), "alias_remove": (40, 730),
                 "delete_alias": (260, 730), "alias_notification": (480, 670),
                 "edit_config": (40, 850), "open_config": (260, 850),
                 "edit_hosts": (40, 970), "open_hosts": (260, 970)}
    fields = [
        config_field("SSH_CONFIG", "SSH config", "~/.ssh/config", "OpenSSH user configuration file"),
        config_field("CUSTOM_HOSTS", "Custom hosts", "~/.ssh/etc_hosts", "Additional hosts in /etc/hosts syntax"),
        config_field("READ_ETC_HOSTS", "Read /etc/hosts", True, "Discover non-local system hosts"),
        config_field("READ_KNOWN_HOSTS", "Read known_hosts", True, "Include previously connected hosts"),
        config_field("SHOW_USERNAMES", "Show usernames", True, "Show User from simple Host blocks"),
        config_field("ENABLE_HISTORY", "Enable history", True, "Record session launches in Alfred workflow data"),
    ]
    return {"bundleid": "com.harshal.alfred-ssh-manager", "category": "Internet", "createdby": "Harshal Ranjhani",
            "description": "Search, alias, inspect and launch OpenSSH sessions.", "disabled": False,
            "name": "Alfred SSH Manager", "version": "1.0.0", "webaddress": "",
            "readme": (ROOT / "README.md").read_text(encoding="utf-8"),
            "objects": objects, "connections": connections,
            "uidata": {uid(name): {"xpos": float(x), "ypos": float(y)} for name, (x, y) in positions.items()},
            "userconfigurationconfig": fields,
            "variables": {f["variable"]: f["config"]["default"] for f in fields}}


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


def make_icon(path):
    # Small, dependency-free terminal icon.
    pixels = []
    for y in range(64):
        row = bytearray()
        for x in range(64):
            color = (32, 37, 47, 255) if 4 <= x < 60 and 4 <= y < 60 else (0, 0, 0, 0)
            if 4 <= x < 60 and 4 <= y < 15:
                color = (59, 76, 94, 255)
            if (18 <= x <= 30 and abs((y - 27) - (x - 18)) <= 2) or (18 <= x <= 30 and abs((y - 39) + (x - 18)) <= 2):
                color = (118, 222, 168, 255)
            if 34 <= x <= 48 and 42 <= y <= 45:
                color = (118, 222, 168, 255)
            row.extend(color)
        pixels.append(b"\x00" + row)
    raw = zlib.compress(b"".join(pixels), 9)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 6, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def build():
    WORKFLOW.mkdir(exist_ok=True)
    with (WORKFLOW / "info.plist").open("wb") as stream:
        plistlib.dump(make_plist(), stream, sort_keys=True)
    make_icon(WORKFLOW / "icon.png")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    shutil.copytree(ROOT / "src", STAGE / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "scripts", STAGE / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(WORKFLOW / "info.plist", STAGE / "info.plist")
    shutil.copy2(WORKFLOW / "icon.png", STAGE / "icon.png")
    shutil.copy2(ROOT / "README.md", STAGE / "README.md")
    shutil.copy2(ROOT / "LICENSE", STAGE / "LICENSE")
    DIST.parent.mkdir(exist_ok=True)
    if DIST.exists():
        DIST.unlink()
    with ZipFile(DIST, "w", ZIP_DEFLATED) as archive:
        for file in sorted(STAGE.rglob("*")):
            if file.is_file():
                entry = ZipInfo(str(file.relative_to(STAGE)), date_time=(2020, 1, 1, 0, 0, 0))
                entry.compress_type = ZIP_DEFLATED
                entry.external_attr = (file.stat().st_mode & 0o777) << 16
                archive.writestr(entry, file.read_bytes())
    print(DIST)


if __name__ == "__main__":
    build()
