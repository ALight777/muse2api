# ALight fork maintenance

`main` follows `czg86389-hub/muse2api/main` without deployment customizations. `codex/alight` is the integration/deployment branch. Each optimization is a distinct commit, independently tested on the upstream base; temporary `codex/pr-*` heads contain only that optimization for independent upstream acceptance.

Current upstream base: `b60f474` (v1.6.10, including the scoped composer Send fix).

| Feature | Independent commit | Integration commit | Upstream review |
| --- | --- | --- | --- |
| Manual/account-based concurrency | `6c739f7` | `6c739f7` | [PR #54](https://github.com/czg86389-hub/muse2api/pull/54) — open |
| Independent queue/generation budgets | `a8fb376` | `a838b07` | [PR #55](https://github.com/czg86389-hub/muse2api/pull/55) — open |
| Video refusal cooldown | `ca16eb7` | `5647ee4` | [PR #56](https://github.com/czg86389-hub/muse2api/pull/56) — open |
| Accurate versions and explicit updates | `193133f` | `79d80f8` | [PR #57](https://github.com/czg86389-hub/muse2api/pull/57) — open |
| Lazy media thumbnails | `f3f3db0` | retained in integration history | [PR #51](https://github.com/czg86389-hub/muse2api/pull/51) |

The optional default proxy file and runtime-overlay build recipe are deployment customizations, separate from these four PRs. Proxy credentials and account data never belong in Git.

## Updating after partial upstream acceptance

1. Fetch both remotes, inspect PR status and actual upstream implementations, then fast-forward fork `main` to upstream. A closed PR is not necessarily merged.
2. Tag the current deployed commit and preserve its image/configuration for rollback. Do not reset the data volume.
3. Merge upstream changes into an integration candidate. For adopted optimizations, prefer the upstream implementation and remove them from the pending-maintenance list. Do not blindly replay every old commit; Git may already recognize identical changes, while squash merges or edited implementations need semantic comparison.
4. If overlap is large, build a fresh candidate from the new upstream base and replay only still-needed independent feature commits. Keep the existing deployment branch/history intact until the candidate is reviewed and tested; do not force-push the active deployment branch.
5. Run each retained feature's regressions and the combined suite. In particular, combine generation queue leases with video cooldown eligibility and keep all runtime modules in the Docker COPY list. Independently mergeable features can still touch the same integration locations.
6. Publish a reviewed integration commit, build an image stamped with its full SHA, wait for active tasks to drain, then switch. Record the deployed SHA and update this table with accepted PR links.

Configuration panels are deliberately independent: concurrency (`data/scheduler.json`), queue budget (`data/generation-queue.json`), and video cooldowns (`data/video-health.json`). The version checker follows `MUSE2API_REPOSITORY` and `MUSE2API_REPO_REF`; deployment uses this fork's integration branch with `MUSE2API_MANAGED_DEPLOYMENT=1`.
