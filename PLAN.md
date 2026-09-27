# Alfred SSH Manager

A fast Alfred 5 workflow for discovering, aliasing, inspecting, and launching SSH sessions.

The workflow should automatically discover hosts from OpenSSH configuration and optional host files, allow the user to define friendly Alfred-specific aliases, and launch SSH/SFTP sessions directly from Alfred.

The workflow should treat OpenSSH as the authority for connection configuration rather than trying to reproduce SSH's configuration resolution logic.

---

# 1. Project Goals

Build an Alfred workflow that makes SSH session management feel like a native Alfred experience.

Primary interaction:

```text
ssh prod
```

Alfred should display matching SSH destinations such as:

```text
★ prod
  production-api — Main production server

production-api
  ubuntu@10.20.30.40 — ~/.ssh/config

prod-db
  10.20.30.55 — ~/.ssh/etc_hosts
```

Pressing Enter should immediately launch:

```bash
ssh production-api
```

in the user's configured terminal.

The workflow must support:

- SSH hosts from `~/.ssh/config`
- SSH `Include` directives
- `/etc/hosts`
- `~/.ssh/etc_hosts`
- optional `~/.ssh/known_hosts`
- user-defined Alfred aliases
- favorites
- descriptions
- tags
- recent sessions
- fuzzy Alfred search
- SSH
- SFTP
- copying commands
- inspecting resolved OpenSSH configuration
- editing configuration files
- alias management from Alfred

---

# 2. Core Design Principle

Do **not** implement an SSH client.

Do **not** attempt to completely interpret `ssh_config`.

The workflow should only perform:

```text
Discovery
    ↓
Presentation
    ↓
Selection
    ↓
Launch OpenSSH
```

OpenSSH itself remains responsible for:

- `HostName`
- `User`
- `Port`
- `IdentityFile`
- `ProxyJump`
- `ProxyCommand`
- `Match`
- wildcard `Host` rules
- authentication
- certificates
- agent forwarding
- connection multiplexing
- host-key verification
- SSH `Include` semantics

For example:

```sshconfig
Host production
    HostName 10.10.10.10
    User ubuntu
    IdentityFile ~/.ssh/prod
    ProxyJump bastion
```

The workflow should execute:

```bash
ssh production
```

rather than constructing:

```bash
ssh -i ~/.ssh/prod -J bastion ubuntu@10.10.10.10
```

This avoids configuration drift and makes the workflow compatible with sophisticated SSH configurations.

---

# 3. Technology Choice

Recommended implementation:

```text
Python 3
```

Reasons:

- preinstalled or readily available on most developer Macs
- simple JSON support
- simple filesystem parsing
- easy Alfred Script Filter integration
- very little code required
- easy for contributors to understand

The code should be structured so the Python implementation can later be replaced with a compiled Go binary if distribution without runtime dependencies becomes important.

Minimum Python target:

```text
Python 3.9+
```

Avoid unnecessary third-party dependencies.

Prefer Python standard library only.

---

# 4. Repository Structure

Recommended repository:

```text
alfred-ssh-manager/
│
├── README.md
├── LICENSE
├── Makefile
├── pyproject.toml
│
├── src/
│   └── alfred_ssh/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── models.py
│       ├── discovery.py
│       ├── ssh_config.py
│       ├── hosts_file.py
│       ├── known_hosts.py
│       ├── aliases.py
│       ├── history.py
│       ├── resolver.py
│       ├── search.py
│       ├── alfred.py
│       └── utils.py
│
├── scripts/
│   ├── ssh_search.py
│   ├── alias_add.py
│   ├── alias_remove.py
│   ├── alias_list.py
│   ├── inspect_host.py
│   ├── record_history.py
│   └── workflow_status.py
│
├── workflow/
│   ├── icon.png
│   ├── info.plist
│   └── assets/
│
└── tests/
    ├── fixtures/
    │   ├── ssh_config
    │   ├── ssh_config.d/
    │   ├── hosts
    │   ├── etc_hosts
    │   ├── known_hosts
    │   └── aliases.json
    │
    ├── test_ssh_config.py
    ├── test_hosts_file.py
    ├── test_aliases.py
    ├── test_discovery.py
    ├── test_search.py
    └── test_alfred_output.py
```

For a simpler first implementation, scripts can directly import files under `src/`.

---

# 5. Workflow Data Storage

Use Alfred's workflow data directory.

Read:

```bash
$alfred_workflow_data
```

The workflow should store mutable user state here.

Example:

```text
~/Library/Application Support/Alfred/Workflow Data/<bundle-id>/
```

Contents:

```text
aliases.json
history.json
settings.json
cache.json
```

Never store mutable user configuration inside the `.alfredworkflow` installation directory.

---

# 6. Bundle Identifier

Use a stable Alfred bundle ID, for example:

```text
com.harshal.alfred-ssh-manager
```

Do not change it after publishing because Alfred workflow data is associated with this ID.

---

# 7. Sources of SSH Hosts

The workflow should aggregate entries from multiple providers.

Initial source order:

```text
1. Alfred aliases
2. ~/.ssh/config
3. ~/.ssh/config Includes
4. ~/.ssh/etc_hosts
5. /etc/hosts
6. ~/.ssh/known_hosts
7. recent history
```

Each result should retain its source metadata.

Example internal model:

```python
HostEntry(
    name="production",
    target="production",
    hostname="10.20.30.40",
    user="ubuntu",
    port=22,
    source="ssh_config",
    source_path="~/.ssh/config",
    description=None,
    tags=[],
    favorite=False,
)
```

---

# 8. Unified Host Model

Create a dataclass similar to:

```python
@dataclass
class HostEntry:
    name: str

    target: str | None = None
    hostname: str | None = None
    user: str | None = None
    port: int | None = None

    source: str = ""
    source_path: str | None = None

    description: str | None = None
    tags: list[str] = field(default_factory=list)

    favorite: bool = False
    alias: bool = False

    last_used: float | None = None
    usage_count: int = 0
```

`target` means the string that should ultimately be passed to:

```bash
ssh <target>
```

For most SSH-config entries:

```text
name = production
target = production
```

For an Alfred alias:

```text
name = prod
target = production
```

---

# 9. Parse ~/.ssh/config

Parse literal `Host` entries.

Example:

```sshconfig
Host production prod-api
    HostName api.example.com
    User deploy

Host staging
    HostName staging.example.com
```

Produce:

```text
production
prod-api
staging
```

Ignore patterns such as:

```sshconfig
Host *
Host *.example.com
Host web-??
Host !production *
```

because they are not enumerable destinations.

Wildcard rules should still work automatically when OpenSSH later connects.

---

# 10. SSH Include Support

Support:

```sshconfig
Include ~/.ssh/config.d/*
Include config.d/*.conf
Include work.conf personal.conf
```

Requirements:

- recursively process include files
- expand `~`
- expand environment variables where appropriate
- expand glob patterns
- avoid infinite include loops
- deduplicate included files
- gracefully ignore nonexistent includes
- support multiple patterns on one `Include` line

Maintain:

```python
seen_files: set[Path]
```

before recursing.

---

# 11. SSH Parsing Rules

Parser should handle:

```sshconfig
Host foo
Host foo bar baz
host foo
HOST foo
```

Configuration keywords are case-insensitive.

Comments must be handled:

```sshconfig
Host foo # production
```

Quoted values should ideally work.

Use `shlex` where practical.

Do not attempt complete OpenSSH grammar compatibility if OpenSSH itself can resolve the configuration later.

---

# 12. OpenSSH Resolution

Implement an optional resolver using:

```bash
ssh -G <host>
```

Example:

```bash
ssh -G production
```

Output can reveal:

```text
host production
hostname 10.20.30.40
user deploy
port 22
identityfile ~/.ssh/prod
proxyjump bastion
```

Create:

```python
resolve_host("production")
```

Use `subprocess.run()` safely.

Never use:

```python
shell=True
```

Use:

```python
subprocess.run(
    ["ssh", "-G", target],
    ...
)
```

Resolution should primarily be used for:

- host inspection
- optional subtitles
- debugging
- displaying effective SSH configuration

It should not be required for every Alfred search result because invoking `ssh -G` for dozens of entries could add latency.

---

# 13. ~/.ssh/etc_hosts

Support a custom hosts file:

```text
~/.ssh/etc_hosts
```

Use `/etc/hosts` syntax:

```text
10.10.0.10 nas nas.home
10.10.0.20 proxmox pve
10.10.0.30 raspberrypi pi homepi

172.20.1.10 devbox development
```

For:

```text
10.10.0.10 nas nas.home
```

create entries:

```text
nas
nas.home
```

with:

```text
hostname = 10.10.0.10
source = custom_hosts
```

SSH command remains:

```bash
ssh nas
```

unless an explicit behavior is configured otherwise.

---

# 14. /etc/hosts

Parse `/etc/hosts` using the same parser.

Skip common local-only entries if desired:

```text
localhost
localhost.localdomain
broadcasthost
ip6-localhost
```

Make filtering configurable.

Default could include all non-local entries while ignoring obvious localhost aliases.

---

# 15. known_hosts Support

Optionally discover hostnames from:

```text
~/.ssh/known_hosts
```

Support normal entries:

```text
github.com ssh-ed25519 ...
server.example.com ssh-ed25519 ...
server.example.com,10.0.0.1 ssh-ed25519 ...
```

Ignore hashed entries:

```text
|1|abc...|xyz...
```

because their hostname cannot be recovered.

Known-host results should have lower ranking than:

```text
aliases
ssh_config
custom hosts
```

because `known_hosts` may contain stale machines.

---

# 16. Alias System

Alfred-specific aliases should be separate from SSH configuration.

Do not modify `~/.ssh/config` when creating an Alfred alias.

File:

```text
$alfred_workflow_data/aliases.json
```

Recommended format:

```json
{
  "prod": {
    "target": "production-api",
    "description": "Main production server",
    "tags": ["work", "prod"],
    "favorite": true
  },

  "db": {
    "target": "production-db",
    "description": "Production PostgreSQL",
    "tags": ["work", "database"],
    "favorite": true
  },

  "nas": {
    "target": "nas.home",
    "description": "Home NAS",
    "tags": ["home"],
    "favorite": false
  }
}
```

Aliases should resolve as:

```text
prod
 ↓
production-api
 ↓
OpenSSH config
 ↓
actual connection
```

---

# 17. Alias Creation

Keyword:

```text
ssha
```

Support syntax:

```text
ssha prod=production-api
```

Optional future syntax:

```text
ssha prod production-api
```

After creation show Alfred notification:

```text
SSH alias created
prod → production-api
```

If alias already exists, update it.

---

# 18. Alias Removal

Keyword:

```text
sshrm
```

Typing:

```text
sshrm prod
```

should show matching Alfred aliases.

Pressing Enter removes the selected alias.

Do not remove actual SSH config entries.

Notification:

```text
SSH alias removed
prod
```

---

# 19. Alias Management Search

Optional keyword:

```text
sshalias
```

Show all aliases.

Actions:

```text
Enter        connect
⌘ Enter      edit alias
⌥ Enter      delete alias
```

This is optional for V1.1.

---

# 20. Primary Alfred Keyword

Main keyword:

```text
ssh
```

Argument should be optional.

Examples:

```text
ssh
ssh prod
ssh db
ssh work
ssh gpu
ssh 10.20
```

When no argument is supplied, show:

```text
favorites
recent sessions
frequently used hosts
```

---

# 21. Alfred Script Filter Output

Output Alfred JSON.

Example:

```json
{
  "items": [
    {
      "uid": "alias:prod",
      "title": "prod",
      "subtitle": "production-api — Main production server",
      "arg": "production-api",
      "autocomplete": "prod",
      "match": "prod production-api production server work prod"
    }
  ]
}
```

Use stable `uid`s.

Examples:

```text
alias:prod
sshconfig:production-api
hosts:nas
knownhosts:github.com
```

Stable UIDs allow Alfred to learn user selection ranking.

---

# 22. Result Metadata

A result should visually communicate its origin.

Examples:

```text
prod
production-api — Main production server · Alias
```

```text
production-api
deploy@api.example.com · SSH Config
```

```text
nas
10.10.0.10 · ~/.ssh/etc_hosts
```

```text
github.com
Known Host
```

Avoid overly long subtitles.

---

# 23. Search

Prefer Alfred's native result filtering when possible.

Populate the Alfred `match` field with:

```text
alias
hostname
target
username
description
tags
source
```

Example:

```json
"match": "prod production-api deploy work production main api"
```

Then searching:

```text
ssh work
```

can match aliases tagged:

```json
"tags": ["work"]
```

---

# 24. Ranking

Preferred baseline ranking:

```text
favorite alias
alias
favorite SSH config
SSH config
custom host file
/etc/hosts
known_hosts
```

Then consider:

```text
usage_count
last_used
Alfred's own UID learning
```

Do not overengineer ranking initially because Alfred already learns selected Script Filter UIDs.

---

# 25. Favorite Hosts

Aliases should support:

```json
"favorite": true
```

Future enhancement:

allow SSH config hosts to be favorited separately using a metadata file:

```json
{
  "production-api": {
    "favorite": true
  }
}
```

Favorites should appear first when running:

```text
ssh
```

with no query.

---

# 26. History

Maintain:

```text
history.json
```

Example:

```json
{
  "production-api": {
    "last_used": 1790503421,
    "usage_count": 83
  },
  "nas.home": {
    "last_used": 1790413000,
    "usage_count": 21
  }
}
```

Record history when a session is launched.

Do not wait for SSH to exit.

Flow:

```text
selection
   ↓
record usage
   ↓
launch terminal
```

---

# 27. Recent Sessions

When the user types:

```text
ssh :recent
```

show entries sorted by `last_used`.

Optional shorthand:

```text
ssh recent
```

Reserve colon-prefixed commands for workflow operations to avoid collisions with actual hostnames.

Recommended commands:

```text
:recent
:fav
:config
:aliases
:refresh
:help
```

---

# 28. Favorites View

```text
ssh :fav
```

Show only favorites.

If no favorites exist:

```text
No favorite SSH hosts yet
```

with instructions in subtitle.

---

# 29. Modifier Actions

Main result:

```text
Enter
```

Launch SSH.

Recommended modifier keys:

```text
⌘ Enter    Copy SSH command
⌥ Enter    Start SFTP session
⌃ Enter    Inspect resolved SSH configuration
⇧ Enter    Open/edit relevant config source
```

Potential later modifier:

```text
⌘⌥ Enter   open new terminal tab/window explicitly
```

---

# 30. SSH Launch

The command ultimately executed should be:

```bash
ssh <target>
```

Avoid manually composing flags.

Use Alfred's Terminal Command action wherever possible so the workflow respects the user's configured terminal.

Possible Alfred workflow:

```text
Script Filter
     ↓
Conditional
     ↓
Terminal Command
```

Terminal command:

```bash
ssh "$target"
```

Ensure arguments are safely passed through workflow variables rather than interpolated in unsafe shell strings.

---

# 31. SFTP

For Option/Alt Enter:

```bash
sftp <target>
```

Open in the configured terminal.

Future enhancement could integrate GUI SFTP applications, but V1 should simply use OpenSSH `sftp`.

---

# 32. Copy SSH Command

Command Enter should place:

```text
ssh production-api
```

on the clipboard.

Notification:

```text
Copied
ssh production-api
```

---

# 33. Inspect SSH Host

Control Enter should run:

```bash
ssh -G <target>
```

Display useful fields.

Do not dump hundreds of lines directly into Alfred.

Extract important values:

```text
Host
HostName
User
Port
IdentityFile
ProxyJump
ProxyCommand
ForwardAgent
ServerAliveInterval
ControlMaster
ControlPath
```

Example Alfred view:

```text
production-api

HostName
10.20.30.40

User
deploy

Port
22

IdentityFile
~/.ssh/prod_ed25519

ProxyJump
bastion
```

Possible output mechanisms:

1. Alfred text view
2. Large Type
3. copy formatted result
4. macOS dialog
5. rerun Script Filter showing individual fields

Best Alfred-native implementation:

rerun into another Script Filter with each resolved property as a result.

---

# 34. SSH Config Editing

Keyword:

```text
sshconf
```

Default action:

open:

```text
~/.ssh/config
```

using macOS default text editor or configured editor.

Potential workflow configuration:

```text
SSH config path
~/.ssh/config

Editor
default
```

Possible editor command examples:

```text
code
zed
vim
nvim
subl
open
```

V1 can simply:

```bash
open ~/.ssh/config
```

---

# 35. Custom Hosts Editing

Keyword:

```text
sshhosts
```

Open:

```text
~/.ssh/etc_hosts
```

If it doesn't exist, create it.

Default header could be:

```text
# Alfred SSH Manager custom hosts
#
# Syntax:
# IP_ADDRESS hostname [aliases...]
#
# Example:
# 10.10.0.10 nas nas.home
```

---

# 36. Workflow Configuration

Expose Alfred Workflow Configuration values.

Suggested options:

## SSH Configuration

```text
SSH Config
~/.ssh/config
```

## Custom Hosts File

```text
~/.ssh/etc_hosts
```

## Read /etc/hosts

```text
true
```

## Read known_hosts

```text
true
```

## Terminal

Initially:

```text
Alfred Default
```

Potential future choices:

```text
Alfred Default
Terminal.app
iTerm2
Ghostty
WezTerm
Warp
Custom
```

## Show usernames

```text
true
```

## Enable history

```text
true
```

---

# 37. Terminal Integration

V1 should rely on Alfred's Terminal Command action.

This automatically gives compatibility with the user's configured Alfred terminal integration.

Do not hard-code Terminal.app unless necessary.

Future advanced integrations can explicitly support:

```text
iTerm2
Ghostty
WezTerm
Warp
kitty
```

---

# 38. Caching

Parsing SSH configuration should be fast, but implement caching if needed.

Cache:

```text
cache.json
```

Include:

```text
source path
modification time
parsed entries
```

Example:

```json
{
  "~/.ssh/config": {
    "mtime": 1790500000,
    "hosts": [...]
  }
}
```

Invalidate when:

```text
mtime changes
included file changes
custom hosts change
aliases change
workflow requests :refresh
```

Do not introduce caching until performance actually requires it.

Correctness is more important than premature caching.

---

# 39. Security Requirements

This workflow handles infrastructure access, so avoid unsafe shell construction.

Never do:

```python
os.system(f"ssh {target}")
```

Never do:

```python
subprocess.run(command, shell=True)
```

Prefer:

```python
subprocess.run(["ssh", "-G", target])
```

For commands passed into Alfred Terminal Command, ensure host values come from known parsed entries or are correctly shell-escaped.

Use:

```python
shlex.quote()
```

when generating terminal command strings.

---

# 40. Do Not Store Credentials

Never store:

```text
passwords
private keys
passphrases
SSH tokens
```

The workflow should rely on:

```text
OpenSSH
ssh-agent
macOS Keychain
1Password SSH agent
other existing SSH agents
```

Aliases should only contain target metadata.

---

# 41. Duplicate Handling

The same destination may appear in:

```text
~/.ssh/config
/etc/hosts
~/.ssh/etc_hosts
known_hosts
aliases
```

Do not blindly remove aliases because two names may intentionally point to the same target.

Deduplication should primarily happen by displayed name/source.

Preferred priority:

```text
alias
ssh config
custom hosts
/etc/hosts
known hosts
```

If the same hostname exists in multiple low-level sources, display the highest-priority source.

An Alfred alias should remain a separate visible entry because its friendly name matters.

---

# 42. Wildcard SSH Hosts

Do not display:

```sshconfig
Host *
Host *.internal
Host web-??
```

unless a concrete host has been discovered elsewhere.

Example:

```sshconfig
Host *.company.internal
    User harshal
    ProxyJump company-bastion
```

and:

```text
/etc/hosts:
10.20.1.10 database.company.internal
```

should result in Alfred showing:

```text
database.company.internal
```

When selected:

```bash
ssh database.company.internal
```

OpenSSH automatically applies the wildcard rule.

---

# 43. Match Directives

Do not attempt to evaluate:

```sshconfig
Match host production
```

or:

```sshconfig
Match exec ...
```

during discovery.

Let:

```bash
ssh
```

and:

```bash
ssh -G
```

evaluate them.

---

# 44. IPv6

Hosts parser must support:

```text
::1 localhost
fd00::1 server
```

Do not assume the first hosts-file token is IPv4.

---

# 45. Hostnames with Ports

Do not treat:

```text
host:2222
```

as a special format unless explicitly supported.

OpenSSH config should be preferred:

```sshconfig
Host dev
    HostName example.com
    Port 2222
```

---

# 46. Username Overrides

Consider supporting ad-hoc input in a later version:

```text
ssh ubuntu@prod
```

If this is implemented, pass it directly to OpenSSH.

Do not modify discovered host data.

V1 can simply search literal entries.

---

# 47. Direct Ad-Hoc SSH

Useful V1.1 feature:

if no matching host exists and the user types:

```text
ssh example.com
```

show:

```text
Connect to example.com
Direct SSH connection
```

Pressing Enter executes:

```bash
ssh example.com
```

Likewise:

```text
ssh ubuntu@example.com
```

This makes the workflow useful for both configured and one-off hosts.

Use validation so workflow command syntax such as:

```text
:recent
```

does not become an SSH destination.

---

# 48. Alfred Workflow Graph

Recommended Alfred graph:

```text
Keyword / Script Filter: ssh
            │
            ▼
       Script Filter
            │
      modifier actions
            │
      ┌─────┼─────┬────────────┐
      │     │     │            │
      ▼     ▼     ▼            ▼
     SSH   Copy  SFTP       Inspect
      │           │            │
      ▼           ▼            ▼
  Terminal     Terminal    Script Filter
```

Additional flows:

```text
Keyword: ssha
     ↓
Run Script
     ↓
Notification
```

```text
Keyword: sshrm
     ↓
Script Filter aliases
     ↓
Run Script
     ↓
Notification
```

```text
Keyword: sshconf
     ↓
Open File
```

```text
Keyword: sshhosts
     ↓
Ensure file exists
     ↓
Open File
```

---

# 49. Search Result Example

For alias:

```json
{
  "uid": "alias:prod",
  "title": "prod",
  "subtitle": "production-api — Main production server · Alias",
  "arg": "production-api",
  "autocomplete": "prod",
  "match": "prod production-api production server work prod",
  "variables": {
    "ssh_target": "production-api",
    "ssh_display_name": "prod",
    "ssh_source": "alias"
  },
  "mods": {
    "cmd": {
      "subtitle": "Copy: ssh production-api",
      "variables": {
        "ssh_action": "copy"
      }
    },
    "alt": {
      "subtitle": "SFTP to production-api",
      "variables": {
        "ssh_action": "sftp"
      }
    },
    "ctrl": {
      "subtitle": "Show resolved SSH configuration",
      "variables": {
        "ssh_action": "inspect"
      }
    }
  }
}
```

---

# 50. Optional Icons

Use visual indicators for source type.

Possible icons:

```text
★ favorite
terminal icon → SSH config
link icon → alias
server icon → hosts file
clock icon → recent
key icon → known_hosts
```

Keep visual style simple and consistent with Alfred.

Avoid excessive custom icons that make search noisy.

---

# 51. Empty Query Experience

Typing:

```text
ssh
```

should produce something useful immediately.

Recommended ordering:

```text
Favorites

Recent

Frequently used

SSH config entries
```

Do not dump hundreds of hosts without useful ranking if the user has a large configuration.

---

# 52. Error Handling

Errors should return Alfred-friendly results rather than stack traces.

Example:

```text
Unable to read ~/.ssh/config
Permission denied
```

Another:

```text
Invalid aliases.json
Press Enter to open file
```

Errors should not prevent other host sources from loading.

For example, if `known_hosts` cannot be parsed, SSH config hosts should still appear.

---

# 53. Logging

Optional debug mode.

Log file:

```text
$alfred_workflow_data/debug.log
```

Disabled by default.

Workflow configuration:

```text
Debug Logging
false
```

Useful information:

```text
files discovered
include paths
parse errors
cache invalidations
search duration
number of results
```

Never log sensitive environment variables or authentication information.

---

# 54. Performance Goal

Target:

```text
<100 ms
```

for normal Script Filter generation on typical configurations.

Avoid running:

```bash
ssh -G
```

for every host during every query.

Do expensive operations only after selection or cache them carefully.

---

# 55. Tests

Unit-test each parser independently.

## SSH config

Test:

```text
single Host
multiple Host values
comments
mixed capitalization
wildcards
negated hosts
Include
nested Include
glob Include
include loops
missing Include
```

## Hosts files

Test:

```text
IPv4
IPv6
multiple aliases
comments
blank lines
invalid rows
```

## known_hosts

Test:

```text
single host
multiple comma-separated hosts
IP address
hashed hosts ignored
markers
```

## Aliases

Test:

```text
create
update
delete
favorite
tags
descriptions
invalid JSON
missing file
```

## Alfred JSON

Validate every generated Script Filter result against expected Alfred structure.

---

# 56. Integration Testing

Use temporary directories.

Example environment:

```text
HOME=/tmp/alfred-ssh-test
```

Create:

```text
~/.ssh/config
~/.ssh/config.d/
~/.ssh/etc_hosts
~/.ssh/known_hosts
```

Then ensure discovery produces deterministic output.

Do not rely on the developer machine's actual SSH configuration for automated tests.

---

# 57. README

README should include:

```text
What it does
Installation
Usage
Sources
Aliases
Keyboard modifiers
Configuration
Custom hosts
Security model
Development
Packaging
Troubleshooting
```

Usage example:

```text
ssh prod
```

Alias example:

```text
ssha prod=production-api
```

Remove alias:

```text
sshrm prod
```

Special commands:

```text
ssh :recent
ssh :fav
ssh :refresh
```

---

# 58. Packaging

Build an Alfred `.alfredworkflow` file.

A `.alfredworkflow` is effectively a packaged workflow directory.

Build script should:

1. clean build directory
2. copy `info.plist`
3. copy Python modules
4. copy scripts
5. copy icons/assets
6. preserve executable permissions
7. zip workflow directory
8. rename archive:

```text
Alfred-SSH-Manager.alfredworkflow
```

Provide:

```bash
make build
```

Output:

```text
dist/Alfred-SSH-Manager.alfredworkflow
```

---

# 59. Development Command

Provide:

```bash
make test
make lint
make build
```

Optional:

```bash
make install
```

which copies or symlinks the workflow into Alfred's workflow directory for local development.

---

# 60. Implementation Phases

## Phase 1 — Core discovery

Implement:

- host model
- SSH config parser
- SSH Include parser
- `/etc/hosts`
- `~/.ssh/etc_hosts`
- deduplication
- Alfred JSON generation

Deliverable:

```text
ssh query
```

returns searchable destinations.

---

## Phase 2 — Alfred workflow

Create:

- Script Filter
- Terminal Command
- stable UIDs
- copy modifier
- SFTP modifier
- workflow icons

Deliverable:

```text
ssh prod
```

opens an SSH session.

---

## Phase 3 — Aliases

Implement:

```text
aliases.json
ssha
sshrm
descriptions
tags
favorites
```

Deliverable:

```text
ssha prod=production-api
ssh prod
```

works.

---

## Phase 4 — History

Implement:

```text
history.json
usage count
last used
:recent
:fav
```

Deliverable:

frequently used hosts become easier to access.

---

## Phase 5 — Inspection

Implement:

```bash
ssh -G
```

and:

```text
Control + Enter
```

for resolved configuration.

Deliverable:

user can inspect exactly how SSH will connect.

---

## Phase 6 — polish

Implement:

- configuration UI
- error handling
- caching if required
- icons
- README
- tests
- package/release process

---

# 61. V1 Definition

The first release is complete when all of the following work:

```text
ssh prod
```

searches hosts.

```text
Enter
```

opens SSH.

```text
⌘ Enter
```

copies the SSH command.

```text
⌥ Enter
```

opens SFTP.

```text
⌃ Enter
```

shows resolved SSH configuration.

The workflow discovers:

```text
~/.ssh/config
SSH Include files
~/.ssh/etc_hosts
/etc/hosts
```

Aliases can be created:

```text
ssha prod=production
```

Aliases can be removed:

```text
sshrm prod
```

Favorites and history work.

No third-party Python packages are required.

---

# 62. V1 Features That Should Be Explicitly Deferred

Do not let the implementation become bloated.

Do not include these in the initial version:

```text
SSH password storage
SSH key management
SSH key generation
SSH key deployment
terminal multiplexing UI
remote file browser
SSH tunneling GUI
AWS instance discovery
GCP instance discovery
Tailscale API integration
Teleport integration
Kubernetes discovery
remote command execution framework
GUI server management
```

These can become optional providers later.

---

# 63. Future Provider Architecture

Design discovery so additional sources can eventually implement something equivalent to:

```python
class HostProvider:
    def discover(self) -> list[HostEntry]:
        ...
```

Providers could later include:

```text
SSHConfigProvider
HostsFileProvider
KnownHostsProvider
AliasProvider
TailscaleProvider
AWSProvider
GCPProvider
DigitalOceanProvider
TeleportProvider
DockerProvider
KubernetesProvider
```

Do not build these now.

Just avoid an architecture that makes them impossible later.

---

# 64. Optional Future Features

Once V1 is stable, consider:

```text
ssh :work
ssh :home
```

using tags.

Potential alias commands:

```text
ssha prod production
ssha --fav prod production
ssha --tag work prod production
```

Potential quick commands:

```text
ssh-copy-id
scp
rsync
mosh
```

For example modifiers could eventually support:

```text
⌘⇧ Enter
ssh-copy-id target
```

but this should not be part of V1.

---

# 65. UX Principle

The workflow should make this:

```bash
grep Host ~/.ssh/config
ssh production-server
```

feel like this:

```text
⌘ Space

ssh prod

Enter
```

The user should never need to remember:

```text
exact hostname
IP address
username
SSH config filename
private key
jump host
port
```

They should only need to remember some fragment such as:

```text
prod
database
nas
home
gpu
client-name
```

OpenSSH handles the connection details.

Alfred handles retrieval.

---

# 66. Final Expected User Experience

Example configuration:

```sshconfig
Host production-api
    HostName api.company.com
    User deploy
    IdentityFile ~/.ssh/company
    ProxyJump bastion.company.com

Host production-db
    HostName db.internal
    User postgres
    ProxyJump bastion.company.com
```

Alias configuration:

```json
{
  "prod": {
    "target": "production-api",
    "description": "Main production API",
    "tags": ["company", "prod"],
    "favorite": true
  },

  "db": {
    "target": "production-db",
    "description": "Production PostgreSQL",
    "tags": ["company", "prod", "database"]
  }
}
```

The user opens Alfred and types:

```text
ssh pr
```

Alfred shows:

```text
★ prod
  production-api — Main production API

production-api
  deploy@api.company.com — SSH Config

production-db
  postgres@db.internal — SSH Config
```

User presses Enter.

A terminal opens and executes:

```bash
ssh production-api
```

OpenSSH automatically applies:

```text
HostName
User
IdentityFile
ProxyJump
```

No connection configuration is duplicated inside Alfred.

---

# 67. Acceptance Criteria

The project should not be considered complete until these scenarios pass.

### Discovery

Given:

```sshconfig
Host foo
Host bar baz

Include ~/.ssh/config.d/*
```

Alfred discovers:

```text
foo
bar
baz
```

and literal hosts inside included files.

It does not display:

```text
*
*.internal
foo-??
```

as concrete destinations.

### Custom hosts

Given:

```text
10.0.0.5 nas nas.home
```

Alfred discovers:

```text
nas
nas.home
```

### Alias

After:

```text
ssha home=nas.home
```

searching:

```text
ssh home
```

returns:

```text
home
nas.home
```

### Connection

Selecting that result executes:

```bash
ssh nas.home
```

not:

```bash
ssh 10.0.0.5
```

unless that is explicitly the alias target.

### Modifier actions

The following work:

```text
Enter      SSH
⌘ Enter    copy
⌥ Enter    SFTP
⌃ Enter    inspect
```

### Includes

Nested includes cannot cause infinite recursion.

### Errors

Malformed secondary files do not prevent healthy sources from appearing.

### Security

No command path uses:

```python
shell=True
```

for SSH configuration resolution or internal commands.

### Performance

Normal host search remains effectively instantaneous.

---

# 68. Instructions for the Coding Agent

Implement the project incrementally.

Do not try to implement every feature in one giant script.

Prioritize:

```text
correct parsing
clean internal model
fast Alfred output
safe command handling
OpenSSH delegation
good UX
tests
```

Whenever there is a choice between manually reproducing OpenSSH behavior and asking OpenSSH itself, prefer OpenSSH.

In particular:

```text
Discovery → workflow code

Connection resolution → OpenSSH

Connection execution → OpenSSH

Authentication → OpenSSH / user's SSH agent
```

Keep Alfred-specific code separate from host discovery logic so the parser and model can be tested outside Alfred.

The final repository should be understandable by another developer without needing to open Alfred to understand how host discovery works.

---

# 69. Recommended First Coding Task

Start by implementing and testing:

```text
src/alfred_ssh/models.py
src/alfred_ssh/ssh_config.py
src/alfred_ssh/hosts_file.py
src/alfred_ssh/discovery.py
src/alfred_ssh/alfred.py
scripts/ssh_search.py
```

Before creating the full Alfred workflow graph, this command should work:

```bash
python scripts/ssh_search.py
```

and output valid Alfred Script Filter JSON.

Only after host discovery and JSON generation are reliable should the actual `.alfredworkflow` nodes be wired together.

---

# 70. Success Condition

The finished project should make SSH destinations behave like searchable Alfred objects rather than commands that the user must memorize.

The architectural separation should remain:

```text
                    Alfred
                       │
                search / aliases
                       │
                       ▼
                 SSH destination
                       │
                       ▼
                    OpenSSH
                       │
                config resolution
                       │
                       ▼
                 Remote machine
```

Alfred knows **what the user wants to connect to**.

OpenSSH knows **how to connect to it**.

That separation is the core design principle of the entire workflow.
