# Oracle Cloud deployment

This runbook installs one FazTestBot process on an Oracle Cloud Infrastructure
(OCI) Always Free Ampere A1 VM. It deliberately starts with a manual deployment;
production CD remains disabled until the first live installation, backup, restart,
and rollback have been verified.

## OCI instance

Create the instance in the tenancy home region with these settings:

- Ubuntu 24.04 Minimal aarch64 image;
- `VM.Standard.A1.Flex`, 1 OCPU and 6 GB memory;
- an Always Free-eligible boot volume (the default 50 GB is sufficient);
- one public IPv4 address for initial administration and outbound Telegram access;
- an SSH public key generated and retained by the operator.

The bot uses Telegram long polling and exposes no HTTP service. Permit inbound TCP
22 only from the operator's current public IP. Do not open ports 80, 443, the
database, or the admin panel. Keep outbound DNS, NTP, HTTPS, and established return
traffic available.

OCI can reclaim idle Always Free compute capacity. Treat this deployment as a
pilot until restart recovery and an off-instance database copy have been proven.
Do not generate artificial load to evade the provider's idle-resource policy.

## Bootstrap

The tracked scripts are intended to be run from a verified FazTestBot release or
from the reviewed deployment branch during the first pilot. On the VM:

```bash
sudo bash deploy/oracle/bootstrap.sh
sudoedit /etc/faztestbot/faztestbot.env
sudo faztestbot-deploy v5.1.0
```

`bootstrap.sh` creates a non-login `faztestbot` account and these boundaries:

| Path | Owner | Purpose |
|---|---|---|
| `/opt/faztestbot/releases/<tag>` | root | immutable release code and virtualenv |
| `/opt/faztestbot/current` | root | atomically selected release |
| `/etc/faztestbot/faztestbot.env` | root:`faztestbot` | deployment secrets and configuration |
| `/var/lib/faztestbot` | `faztestbot` | SQLite, backups, logs, locks, and generated files |

Never paste a populated environment file into cloud-init metadata or commit it to
Git. After editing it, verify that it is not group/world writable:

```bash
sudo stat -c '%a %U %G %n' /etc/faztestbot/faztestbot.env
```

The expected result is `640 root faztestbot`.
Each immutable release contains only a root-owned `.env` symlink to this separate
file. The service does not ask systemd to parse secrets into its manager
environment; application configuration reads the access-restricted file directly.

## Verification

```bash
sudo systemctl status faztestbot.service --no-pager
sudo -u faztestbot /opt/faztestbot/current/.venv/bin/python -m scripts.liveness --json
sudo journalctl -u faztestbot.service --since '-10 minutes' --no-pager
```

Then send `/start` to the real bot and exercise one read-only module. A live smoke
test is the only step that confirms Telegram connectivity; the offline probe never
sends the token or contacts Telegram.

Reboot the VM once during the pilot and repeat both the liveness and Telegram
checks. The service is enabled at boot and restarts on process failure.

## Updates and rollback

Install only a published `vX.Y.Z` release:

```bash
sudo faztestbot-deploy vX.Y.Z
```

The deployer serializes updates, downloads the release archive and checksum over
HTTPS, verifies SHA-256, installs exact Python dependencies into a new directory,
runs readiness, stops the old service, creates a SQLite backup, atomically changes
the `current` symlink, and requires liveness within 30 seconds.

If liveness fails, it restores the previous code link and attempts to restart it.
It intentionally does not restore a database automatically because doing so could
discard updates received after the backup. Follow [database.md](database.md) for a
reviewed database restore.

Installed releases are retained for operator-controlled rollback and cleanup. Do
not delete the current target or the immediately previous release.

## Backup boundary

Application backups under `/var/lib/faztestbot/backups` protect against a bad
migration but not loss of the VM or boot volume. Before calling this production,
copy verified SQLite backups to OCI Object Storage or another independent target,
define retention, and perform one restore drill. Credentials for that copy must
not be stored in the repository.

## Deferred CD

Do not add an unattended push-to-production workflow during the pilot. The later
CD stage must deploy only protected `master` release tags, use a GitHub Environment
approval, serialize deployments, keep credentials outside repository secrets when
possible, and report the liveness and rollback result.
