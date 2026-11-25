# Control plane

One localhost page that shows every setting in this skill package. Standard
library plus PyYAML, which the repo already needs. Nothing is sent off the
machine: the server binds 127.0.0.1 only.

## Run

```
python control-plane/serve.py            # opens http://127.0.0.1:8791/
python control-plane/serve.py --port 8792 --no-open
python control-plane/serve.py --selftest # asserts the discovery still works
```

Stop it with ctrl+c. Do not run it as a service or bind it to another host.

## What it shows

Seven sections, all searchable from the one filter box:

- **Environment variables** — every variable name any file in the repo reads,
  with file:line provenance and whether it is currently set. Names that look
  like secrets get a `reveal` button that reads the value from this process
  environment only.
- **Code settings registry** — the settings that are hardcoded inside scripts,
  with file, line, and what each one controls. Read from
  `.scratch/control-plane/inventory-*.md`, so the page and the audit never
  disagree.
- **Config files** — every YAML, template, dotenv and database in the repo,
  discovered by walking the tree. `values` shows the parsed document plus the
  raw text. Docs and data dumps are hidden behind the checkbox because they
  are not settings.
- **Databases** — every `.db` file, its tables, row counts, and the contents of
  small config tables. `shared/applications.db` is the live one; the two
  0-byte files at the repo root and `shared/apps.db` are strays.
- **Cron and scheduled tasks** — the live `hermes cron list` output. This
  bundle's cron is Hermes-internal, so the Windows Task Scheduler holds
  nothing for it; the earlier schtasks version of this section was reading the
  wrong source and always showed zero.
- **Security hooks** — live `hermes hooks list` and `hermes hooks doctor`,
  which is where the submit gate and the database-ownership gate are declared.
  A hook edited after approval shows up here as "script modified since
  approval", which is the state the Rule 1 submit gate was in until it is
  re-approved.
- **Cron health** — live output of the two existing read-only CLIs:
  `cron/executions.py report` (which job went silent, which never ran) and
  `cron/scripts/verify-cron-config.py` (live config against the desired state).
  Exit code 1 is shown as-is, because that is what those tools do when they
  find a problem.
- **Gates and rules in prose** — every `## Rule` heading from
  `shared/pipeline-rules.md`, `shared/pipeline-rules-addendum.md` and
  `security/security-setup.md`, with the full text one click away. These are
  the rules that no YAML file records.

A full build walks 362 files, reads the database and runs two cron CLIs, which
takes tens of seconds on this machine. So the page never waits for it: it
renders whatever the cache holds and re-renders itself when the build lands.
`refresh data` forces a rebuild, and a rebuild never blocks the page.

## What it can change

Only two write paths exist, and only for YAML config files and cron JSON:

- every save parses first and refuses an unparseable or empty document,
- every save copies the previous file into `control-plane/backups/`,
- writes go through a temp file and an atomic rename,
- a path outside the repo, or a file that is not YAML or cron JSON, is refused.

Anything under **Code settings registry** is source code. The page shows where
it lives so you can change it deliberately, not through a form.

## Limits

- The registry is only as complete as the inventory markdown. If you add a new
  hardcoded setting, add a row.
- Secret values stored in the Windows registry are shown by name and storage
  location only; the page never reads them.
- The page is read-mostly on purpose: editing `shared/target-profile.yaml` from
  here changes what the next discovery and scoring run does.
- The cron health section reports drift; it never fixes it. Two things it found
  on 2026-11-24 are worth acting on: five cron jobs are pinned to
  `stealth/ox-alpha` while the desired state says `poolside/laguna-xs-2.1:free`,
  and the `Bi-monthly configuration drift check` job is not registered at all,
  which is why nobody had seen that drift before.