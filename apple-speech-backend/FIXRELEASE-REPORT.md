# apple-asr wheel release-attach: idempotency fix — report

Repo: `/Users/clkao/git/asr/apple-asr`
Change commit: `f2aea1ac394d945a695c104cebda1d0a11910341` on `main` (pushed to `origin/main`)
Tag `v0.1.4`: **unchanged** — annotated tag object `72ef23b6f16c96ddb9bdcc641c7e1548884a77ab` → commit `73f0d31f33ec8cf8ea56c55f3fa4ae48a6dbddeb`. No new tags. No package code, version, or clock/word-clamp changes. No PyPI publish path touched.

## 1. Root cause (confirmed by log, not guessed)

Run `35835189038` (push, tag `v0.1.4`, sha `73f0d31`) attach step:

```
gh release view "$GITHUB_REF_NAME" >/dev/null 2>&1 ||
  gh release create "$GITHUB_REF_NAME" --verify-tag --generate-notes
gh release upload "$GITHUB_REF_NAME" dist/*.whl --clobber
...
HTTP 422: Validation Failed (https://uploads.github.com/repos/clkao/apple-asr/releases/394429135/assets?label=&name=apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl)
ReleaseAsset.name already exists
##[error]Process completed with exit code 1.
```

Note the URL: gh resolved the release **id** 394429135 correctly, so this is *not* a tag-resolution failure. `--clobber` looks for the existing asset through the release-**by-tag** view; that view can report an empty `assets` array while the asset is really on the release, so clobber deletes nothing and the plain upload then collides on the name. Reproduced locally with the pre-fix command (see §3).

Observed tag-view staleness (the exact trap, captured *before* the fix, asset definitely present):

```
$ gh api repos/clkao/apple-asr/releases/tags/v0.1.4 --jq '{id, assets:[.assets[].name]}'
{"id":394429135,"assets":[]}                                   # <-- stale / empty
$ gh api repos/clkao/apple-asr/releases/394429135/assets --jq '.[]|{id,name,size,state}'
{"id":583304090,"name":"apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl","size":133474,"state":"uploaded"}
```

So the workflow now reads and verifies assets **only** through `/releases/<id>/assets`.

## 2. The diff (`73f0d31..f2aea1a`, `.github/workflows/wheel.yml`, only file changed)

```diff
@@ -51,8 +51,55 @@ jobs:
         env:
           GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
         run: |
+          set -euo pipefail
+          tag="$GITHUB_REF_NAME"
+
           # --verify-tag: never create a release for a tag that does not exist
           # (workflow_dispatch runs are excluded by the `if:` above anyway).
-          gh release view "$GITHUB_REF_NAME" >/dev/null 2>&1 ||
-            gh release create "$GITHUB_REF_NAME" --verify-tag --generate-notes
-          gh release upload "$GITHUB_REF_NAME" dist/*.whl --clobber
+          gh release view "$tag" >/dev/null 2>&1 ||
+            gh release create "$tag" --verify-tag --generate-notes
+
+          # Always resolve assets through /releases/<id>/assets. Do NOT rely on
+          # the `assets` array of /releases/tags/<tag> (what `gh release view`
+          # returns): GitHub can serve that view with an EMPTY `assets` list
+          # while the asset really is on the release. That staleness is what
+          # makes `gh release upload --clobber` fail on a re-run with
+          # "HTTP 422 ... ReleaseAsset.name already exists" - clobber looks for
+          # the existing asset via the tag view, finds none, and then the plain
+          # upload collides. So: resolve the id once, and read/verify against it.
+          rel_id=$(gh api "repos/$GITHUB_REPOSITORY/releases/tags/$tag" --jq .id)
+
+          shopt -s nullglob
+          wheels=(dist/*.whl)
+          if [ "${#wheels[@]}" -ne 1 ]; then
+            echo "::error::expected exactly one wheel in dist/, found ${#wheels[@]}"
+            exit 1
+          fi
+          wheel=$(basename "${wheels[0]}")
+
+          # Idempotent re-runs: drop any pre-existing asset under the same name
+          # before uploading, otherwise the upload 422s on the name collision.
+          # (Nothing to delete on a first run.)
+          asset_id=$(gh api "repos/$GITHUB_REPOSITORY/releases/$rel_id/assets" \
+            --jq ".[] | select(.name == \"$wheel\") | .id" || true)
+          if [ -n "$asset_id" ]; then
+            echo "deleting pre-existing asset $wheel (id $asset_id)"
+            gh api -X DELETE "repos/$GITHUB_REPOSITORY/releases/assets/$asset_id"
+          else
+            echo "no pre-existing asset named $wheel"
+          fi
+
+          echo "uploading $wheel to release $tag (id $rel_id)"
+          gh release upload "$tag" "dist/$wheel"
+
+          # Self-verify against the authoritative endpoint: the release must end
+          # with exactly one asset, named as expected.
+          total=$(gh api "repos/$GITHUB_REPOSITORY/releases/$rel_id/assets" --jq 'length')
+          matching=$(gh api "repos/$GITHUB_REPOSITORY/releases/$rel_id/assets" \
+            --jq "[.[] | select(.name == \"$wheel\")] | length")
+          if [ "$matching" != "1" ] || [ "$total" != "1" ]; then
+            echo "::error::expected exactly one asset named $wheel; found matching=$matching total=$total"
+            gh api "repos/$GITHUB_REPOSITORY/releases/$rel_id/assets" --jq '.[].name'
+            exit 1
+          fi
+          echo "ok: release $tag carries exactly one asset, $wheel"
```

Preserved: release creation when missing with `--verify-tag`, the `if: startsWith(github.ref, 'refs/tags/')` guard (so `workflow_dispatch` still attaches nothing), and no PyPI publish. `--clobber` is gone because the delete is now explicit and verifiable.

## 3. Verification — and the one thing that could NOT be done as specified

### 3a. The prescribed method does not observe the fix (GitHub Actions semantics)

`gh run rerun 35835189038` was executed as instructed. Result: **still failure**, because a re-run replays the workflow definition pinned to the *original run's ref/SHA* (`73f0d31`, i.e. the tag's old YAML) and does **not** pick up a newer `main`. Proof from the new run's log — the old script text is echoed verbatim and there is no delete line:

```
2026-09-23T08:15:36.9053060Z gh release view "$GITHUB_REF_NAME" >/dev/null 2>&1 ||
2026-09-23T08:15:36.9053520Z   gh release create "$GITHUB_REF_NAME" --verify-tag --generate-notes
2026-09-23T08:15:36.9053930Z gh release upload "$GITHUB_REF_NAME" dist/*.whl --clobber
2026-09-23T08:15:38.6512520Z HTTP 422: Validation Failed (https://uploads.github.com/repos/clkao/apple-asr/releases/394429135/assets?label=&name=apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl)
2026-09-23T08:15:38.6529210Z ReleaseAsset.name already exists
```

Making that particular run green would require either moving the `v0.1.4` tag or creating a new tag to carry the new workflow file — both explicitly out of scope ("do not create new tags; the tag stays where it is"). Making it green by deleting the asset *without* re-adding the fixed step would be a green run of the **old** code and would show none of the requested delete-then-upload lines, so it was rejected as misleading.

The run therefore stays red, and its re-run was the only product of it. Everything below is the substitute verification of the *new* step, plus one genuine GitHub-side run of the new YAML.

### 3b. The exact new step script, executed end-to-end against the live `v0.1.4` release

The `run:` block was extracted mechanically from the committed `wheel.yml` (`/tmp/attach.sh`), `bash -n` clean, and executed exactly as Actions does (`/bin/bash -e`, same `GITHUB_REF_NAME`/`GITHUB_REPOSITORY`/token, from a directory that is a git checkout of `clkao/apple-asr`). The wheel in `dist/` was the release's own asset bytes (downloaded via `/releases/394429135/assets`), so the release content is unchanged — only deleted and re-added, which is the point of the order.

Pre-fix command, same checkout (bug reproduced outside CI, exit 1):

```
$ gh release upload v0.1.4 dist/*.whl --clobber -R clkao/apple-asr
HTTP 422: Validation Failed (https://uploads.github.com/repos/clkao/apple-asr/releases/394429135/assets?label=&name=apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl)
ReleaseAsset.name already exists
exit=1
```

New step, **run 1** (asset already present → delete-then-upload path):

```
deleting pre-existing asset apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl (id 583304090)
uploading apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl to release v0.1.4 (id 394429135)
ok: release v0.1.4 carries exactly one asset, apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl
exit=0
```

New step, **run 2** — this is the "re-run for an existing tag" case, the exact thing that used to go red:

```
deleting pre-existing asset apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl (id 583314178)
uploading apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl to release v0.1.4 (id 394429135)
ok: release v0.1.4 carries exactly one asset, apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl
exit=0
```

### 3c. Authoritative asset listing (after both runs) — `/releases/<id>/assets`, not the tag view

```
$ gh api repos/clkao/apple-asr/releases/394429135/assets --jq '.[]|{id,name,size,state,created_at}'
{"created_at":"2026-09-23T08:16:18Z","id":583314360,"name":"apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl","size":133474,"state":"uploaded"}
```

Exactly one asset, expected name, `state: uploaded`. (For contrast, the same query in §1 showed the tag view claiming zero assets while this endpoint listed one — the workflow no longer depends on the tag view.)

Asset integrity: the attached wheel's *contents* are identical to a freshly CI-built wheel for the same source (`diff -r` of the two extracted wheels: no differences; sizes both 133474). The two are not byte-identical as containers (`sha256 d1d6a908…` attached vs `f1ca6f46…` freshly built) — zip container metadata only; the wheel itself is not byte-reproducible.

### 3d. GitHub-side run of the new workflow YAML (extra, because 3a cannot be satisfied)

`gh workflow run wheel.yml --ref main` → run `35836217834`, sha `f2aea1a`, **conclusion: success**. Steps: build → show artifact → upload-artifact all success, and `Attach the wheel to the release for the tag` = **skipped** — GitHub accepted and parsed the new file, and the tag-only guard is intact (a dispatch run still publishes nothing). This validates the YAML/step schema at the Actions level; it deliberately does not exercise the attach path (see 3a).

### 3e. CI (`ci.yml`) for the same commit is unaffected

- `ci.yml` run `35835189293` (push, tag `v0.1.4`, sha `73f0d31`) — **success**
- `ci.yml` run `35835184753` (push, `main`, sha `73f0d31`) — **success**
- Re-running the wheel workflow does not touch `ci.yml`; the wheel re-run changed no `ci.yml` state.
- My push of the workflow-only change (`f2aea1a`) triggered `ci.yml` run `35836055261` on `main` — **success** (no package code touched).

## 4. Tooling / validation performed

- `bash -n` on the extracted `run:` block — clean; then executed as `/bin/bash -e` against the live release (§3b).
- YAML parses (ruby `YAML.load_file`) and GitHub's own parser accepted the file (run `35836217834`, §3d).
- `git status`: clean, nothing staged, `main == origin/main` at `f2aea1a`; tag untouched.

## 5. Unresolved / open

1. **Run `35835189038` remains red.** It re-ran the tag-pinned old YAML and always will. Cannot be made green without moving the `v0.1.4` tag or creating a new tag — both excluded by the task constraints. The next real `v*` tag push will run the fixed YAML and exercise the delete-then-upload path in CI; the fix itself is verified by §3b/§3c.
2. The attach step asserts `total == 1` as well as `matching == 1` (a stricter reading of "exactly one asset of the expected name"). If a future release ever carries a second, non-wheel asset, the step will fail loudly on `total`. Intentional, but flagging it as the one place the check is stricter than the literal wording.
3. `gh release upload --clobber` mis-detecting existing assets is an upstream `gh` (2.97.0) behaviour; the workflow no longer depends on clobber at all, so it is not worked around elsewhere.
