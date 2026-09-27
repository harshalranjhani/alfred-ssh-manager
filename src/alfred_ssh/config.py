import os
from dataclasses import dataclass
from pathlib import Path

BUNDLE_ID = "com.harshal.alfred-ssh-manager"


def expanded_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value)))


def enabled(name: str, default: bool = True) -> bool:
    return os.environ.get(name, str(default)).strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class Settings:
    ssh_config: Path
    custom_hosts: Path
    etc_hosts: Path
    known_hosts: Path
    data_dir: Path
    read_etc_hosts: bool = True
    read_known_hosts: bool = True
    show_usernames: bool = True
    enable_history: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        home = Path.home()
        return cls(
            ssh_config=expanded_path(os.environ.get("SSH_CONFIG", "~/.ssh/config")),
            custom_hosts=expanded_path(os.environ.get("CUSTOM_HOSTS", "~/.ssh/etc_hosts")),
            etc_hosts=expanded_path(os.environ.get("ETC_HOSTS", "/etc/hosts")),
            known_hosts=expanded_path(os.environ.get("KNOWN_HOSTS", "~/.ssh/known_hosts")),
            data_dir=expanded_path(os.environ.get("alfred_workflow_data", str(home / "Library/Application Support/Alfred/Workflow Data" / BUNDLE_ID))),
            read_etc_hosts=enabled("READ_ETC_HOSTS"),
            read_known_hosts=enabled("READ_KNOWN_HOSTS"),
            show_usernames=enabled("SHOW_USERNAMES"),
            enable_history=enabled("ENABLE_HISTORY"),
        )
