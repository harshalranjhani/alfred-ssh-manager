# Alfred SSH Manager

Search and launch SSH destinations from Alfred while OpenSSH handles connection settings and authentication. The workflow discovers literal `Host` entries in `~/.ssh/config` and its includes, `~/.ssh/etc_hosts`, `/etc/hosts`, and optionally `~/.ssh/known_hosts`. It also stores friendly aliases, favorites, and session history in Alfred's workflow data directory.

## Install

Requires Alfred 5.5 or newer with the Powerpack, macOS, Python 3.9 or newer available at `/usr/bin/python3`, and OpenSSH. Double-click [Alfred-SSH-Manager.alfredworkflow](dist/Alfred-SSH-Manager.alfredworkflow) to import the built workflow. If building from source, run `make build` first. Alfred may ask you to approve the workflow on import.

## Use

Type `ssh` to see favorites and recent hosts, or `ssh prod` to search names, targets, usernames, descriptions, and tags. Search words may be partial or fuzzy. Selecting a host passes its target to OpenSSH; an alias named `prod` targeting `production-api` runs `ssh production-api` and lets OpenSSH resolve its config.

| Key | Action |
| --- | --- |
| Return | Open SSH in Alfred's configured terminal |
| Command + Return | Copy the quoted SSH command |
| Option + Return | Open SFTP in Alfred's configured terminal |
| Control + Return | Show selected fields from `ssh -G` in Alfred's Text View |
| Shift + Return | Open the entry's source file in the default editor |

Useful searches: `ssh :recent`, `ssh :fav`, `ssh :aliases`, `ssh :config`, `ssh :help`, and `ssh :refresh`. The workflow rereads files on every search, so `:refresh` only confirms this. If a normal query has no match, the workflow offers a direct SSH connection to that token.

If a direct connection fails, it may still appear in Recent because the workflow records a launch before SSH exits. Type `sshforget`, find the target, and press Return to remove its history entry. This does not delete SSH config hosts or Alfred aliases.

## Guided key setup

Type `sshsetup` to see key tools and known hosts. Select a host (or type `sshsetup user@server`) and press Return to generate/reuse this Mac’s `~/.ssh/id_ed25519`, install its public key, and test public-key login. Terminal handles the passphrase, server-password, and host-trust prompts. Use a passphrase when prompted; the workflow never stores passwords. Command + Return tests existing access without installing a key.

For server-to-server access, type `sshsetup source > destination`, for example `sshsetup deploy@build-box > deploy@app-box`. Alfred aliases work on both sides. The source generates/keeps its own key; only its public key passes through your Mac to the destination. Your Mac must already be able to authenticate to both servers (password login is fine). The final test runs on the source using the destination’s hostname, user, and port resolved on this Mac. The source needs direct network access; local ProxyJump/ProxyCommand settings are not copied to it. A remote passphrase or host-trust prompt may appear during that test.

The empty `sshsetup` menu also offers key generation, public-key copy, and fingerprint display. These tools use the standard Ed25519 key path; custom IdentityFile keys and other key types are not managed. Existing complete pairs are reused; incomplete pairs stop with an error instead of being overwritten. Copy and fingerprint require an existing public key.

Installation appends to the destination account’s `~/.ssh/authorized_keys`, avoids adding the same Ed25519 key twice, and preserves existing entries and restrictions. It sets `.ssh` permissions to 700 and `authorized_keys` to 600, following [OpenSSH’s public-key setup guidance](https://man.openbsd.org/ssh). Remote hosts need a POSIX shell and OpenSSH; servers using a custom AuthorizedKeysFile or managed key service require manual setup. Setup does not enable password login or change server configuration. If the final test fails, installed keys remain in place and the terminal reports the error; retrying is safe.

## Aliases

Use `ssha prod=production-api` to create or update an Alfred alias, then `ssh prod` to connect. Add metadata with `ssha prod=production-api --fav --tag work --description "Main production server"`. Use `sshrm prod` to find and remove aliases. These commands only change `aliases.json`, never SSH config. You can also edit that JSON file from an alias result with Shift + Return. Existing favorite, tags, and description are preserved when updating an alias unless replaced by supplied options.

## Host files and configuration

`sshhosts` opens `~/.ssh/etc_hosts` and creates it if needed. Each row uses `/etc/hosts` syntax, for example `10.10.0.10 nas nas.home`. Both names appear in search; selecting `nas.home` executes `ssh nas.home`. `sshconf` opens `~/.ssh/config`. Paths and source toggles are available in Alfred's Workflow Configuration.

Known-host discovery ignores hashed names and bracketed port entries. Literal SSH `Host` names are discoverable; wildcard and `Match` rules are left to OpenSSH at connection time. Simple `HostName`, `User`, and `Port` values provide search metadata, while `ssh -G` supplies the effective values for inspection.

Alfred stores mutable files under `$alfred_workflow_data`: `aliases.json` and `history.json`. The workflow data directory stores no credentials or keys; setup keeps keys in the owning machine’s `~/.ssh`. Generated terminal command arguments are shell quoted; `ssh -G` runs with a subprocess argument list.

## Development

Run `make test`, `make build`, and `make lint`. The package is written to `dist/Alfred-SSH-Manager.alfredworkflow`. Search can be exercised without Alfred: `python3 scripts/ssh_search.py prod`. Tests create temporary SSH files and do not depend on the machine's live SSH configuration.

To publish a release, push a version tag such as `v1.0.0`. The GitHub Actions release workflow tests and builds that revision, creates a GitHub release, and attaches the `.alfredworkflow` file. Publishing a release manually also triggers an asset build if the release has no workflow file yet.

If a source file is unreadable or aliases JSON is invalid, Alfred shows a warning row while continuing to load healthy sources. If Python is unavailable at `/usr/bin/python3`, install the macOS Command Line Tools or change the interpreter path in `tools/build.py` and rebuild. To change the terminal, use Alfred's Features → Terminal settings; the workflow uses Alfred's Terminal Command action.
