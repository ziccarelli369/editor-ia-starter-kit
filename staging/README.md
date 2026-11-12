# Staging

Review versions only, one folder per project: `<yyyy-mm-dd>-<slug>/`.
`node scripts/deliver.mjs <id> --stage ...` writes each round here as
`<name>-v<N>-<kind>`, so the user can compare versions. The approved version
goes to `outbox/` with `--promote <N>`.

Staging is temporary. `npm run clean-staging -- [<id>] [--older-than <days>]`
moves these files to the Recycle Bin or trash.
