# Network Posture — what phones home, and the toggle that keeps it at zero

Answers a direct question honestly: **can the user turn off every
connection from this tool to a server, and have every pipeline and
function work solely on their own machine?**

Yes. That is the shipped default, and nothing needs to be turned off —
there is nothing to turn off. This document is the inventory that proves
it, plus the three env vars that are the only way to ever make an
outbound product connection exist.

## The guarantee

The tool makes **zero automatic connections to any server it ships
with**. No telemetry, no license check, no ledger sync, no update poll,
no heartbeat. The pipeline runs on the user's machine against the
user's own database; every cron job, gate, and script in this package is
local.

The only outbound HTTP in the entire tree is the pipeline's actual
job: fetching **job postings and public research** from third-party
sites (Greenhouse, Ashby, Wellfound, Lever, O*NET, Adzuna, RSS feeds).
Those are the data sources the user configured discovery to read, not a
back-channel. Every one of them is named in `shared/sources.yaml` /
`shared/discovery_queries.yaml` and visible in the pipeline's logs.

## Complete inventory of outbound connections

| Surface | What it contacts | When it runs | Shipped in the live tree? |
|---|---|---|---|
| Licensing installer (`installer.py`) | `hermes-licensing.*.workers.dev` — `/v1/activate`, `/v1/bundles`, `/v1/seats/release` | Only when the user runs it manually with `--key` or `--release`. `--status` is local-only (Ed25519 verification against a pinned public key, 14 days + 30-day grace offline) | No — lives in the build/dist folder, not in `hermes/skills/job-hunting` |
| Federated ledger client (`federated/client.py sync`) | `JH_API` `/v1/telemetry` + `/v1/ledger/sync` | Only when invoked manually, **and only if `JH_TOKEN` is set** — without a token it stages locally and never sends | No — not installed in the live tree, no cron job references it |
| Everything else — cron jobs, wake gates, backup scripts, crawlers, permission engine, orchestrator | Nothing | — | — |

## The three env vars that could change this

These are the only switches that can ever create an outbound product
connection. The local-only posture is simply: **leave them unset.**

| Env var | Read by | Effect if set |
|---|---|---|
| `JH_TOKEN` | `federated/client.py` | Unlocks actual sending of the staged telemetry/ledger batches |
| `JH_API` | `federated/client.py`, `installer.py` | Points the client at a live ledger/licensing server (default is a placeholder, `api.example.com`) |
| `JH_PUBLIC_KEY` | `installer.py` | Verifies licence tokens; harmless to set, only relevant at activation |

A fresh install has none of these set. Nothing in the repo, no cron
job, and no script writes or exports them. If they are ever set, it is
because the user chose to — and the tool should make that choice
visible, not silent (see the settings catalog entry below).

## What is NOT outbound

- **No telemetry.** The worker defines `/v1/telemetry`, but only the
  federated client would call it, and only with a token.
- **No license checks at runtime.** The installer verifies the stored
  token locally against the pinned public key; the skill tree never
  contacts a licensing server. A licence that cannot be checked pauses
  nothing on the local machine.
- **No update polling, no version pings, no analytics.**

## What still needs the network, and why that is the product

Discovery, JD parsing of live postings, and company research are the
pipeline's reason to exist — they read third-party sites the user told
it to read. "Fully local" does not mean "no network at all"; it means
**no connection to the tool's own server infrastructure, of which there
is none in a local install**. If the user wants the tool to never make
any network call whatsoever, the answer is: don't run the discovery and
research steps, or point them at local fixtures — the rest of the
pipeline (resume match, cover letter, QA gates, approval, submission
drafts, analytics, career planning) is entirely offline.

## Keeping the guarantee verifiable

- `tools/ensure-dev-env.py` checks the environment (sqlite3 CLI, venv
  packages, deployed scripts, skill tree). If a future version ever
  needs to verify the posture, the three env vars above are the only
  product-network inputs it would need to look at — they are the entire
  surface.
- The MANIFEST of the installed tree is checksum-verified at install
  (local, `MANIFEST.json` + `MANIFEST.sig`) — integrity is pinned
  without any runtime server contact.
- If the federated loop is ever enabled (ledger deployed, token
  supplied), the client's own design already stages every batch in a
  table the user can read before anything leaves the machine
  (`outbound_telemetry`), and "offline is the normal case" — with no
  ledger contact the node uses an uninformative prior and behaves
  exactly like the siloed system.
