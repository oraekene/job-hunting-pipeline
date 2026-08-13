# 12 — backup.sh must not fail on empty retention dirs

**What to build:** The nightly tier-1 backup was alarming Telegram with
"Script exited with code 2" every night — the snapshot itself had succeeded
("db ok") — because the retention prune lines
(`ls -1dt "$DEST"/weekly/* | tail | xargs rm -rf`) exit 2 on an unmatched
glob, and `set -o pipefail` turned that into a whole-script failure. Prune
lines now tolerate empty dirs; a successful snapshot exits 0.

**Blocked by:** None — can start immediately

**Status:** done

- [x] Reproduced the crash: prune pipeline on empty dirs exits 2 under
  pipefail (script never reaches the final "[SILENT] backup ok")
- [x] The three prune lines append `|| true`, with a comment explaining
  why (empty dir is not a backup failure)
- [x] Verified with a real run against empty daily/weekly/monthly dirs:
  snapshot written, exit 0, "[SILENT] backup ok" printed
- [x] Live copy (`hermes/scripts/backup.sh`) and bundle copy
  (`security/scripts/backup.sh`) kept byte-identical (hash-checked)
- [x] BACKUP_GPG_RECIPIENT warning left as-is: non-fatal, surfaces the
  unencrypted-snapshot decision to Kenechukwu
