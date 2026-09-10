# Integration branch disposition audit

Date: 2026-09-10. Scope: every commit in `origin/main..feat/apple-silicon-backends` (121).

Method: exact patch-id matching (`git cherry`) against origin/main and each in-flight branch; subject matching against the upstream ported commits (#422/#423 era: 0e3e624..0a6996f under different SHAs); content checks for the rest (file presence, behavior grep on main's engine, diff-stat against the #426 head). Zero integration commits are literal ancestors of any target branch — every disposition here is content-based.

Compared refs: origin/main (363e4f6), fork/spacedock-ensign/mlx-qwen3-asr-backend (#425, 24082a0), fork/spacedock-ensign/nemotron-mlx-asr-backend-rebased (#426, 1842f4c), wlk/calibration-export (cb667e6, PR #448), wlk/display-unification (513b6fa, PR #449), wlk/tui-view (aae6299).

## Summary

- **merged-upstream: 28**
- **in-flight-PR: 4**
- **unique-simul-frontier: 3**
- **unique-diarization: 3**
- **unique-client: 29**
- **unique-eval: 4**
- **local-custom: 7**
- **superseded-display: 35**
- **superseded-nemotron: 5**
- **unsure: 3**

The unique-* lists are the carve-out plan for the branch retirement. Three commits are `unsure`, each with a named resolver.

## merged-upstream (28)

| commit | subject | evidence |
|---|---|---|
| 3aa3fa4 | feat: generic mlx-llm-mt translation backend (Hunyuan-MT, TranslateGemma) | #422 adapted: translation_mlx_llm_mt.py + translation_hunyuan_mlx.py on main (9c4099b/a2c6039) |
| 3b55acf | feat: simultaneous-MT variant for mlx-llm-mt via AlignAtt commit policy | #423 adapted: translation_mlx_llm_mt_simul.py on main |
| 5399dd4 | feat: per-(model, src, target) calibration registry with silent deactivation | upstream 9ed0eae same subject; NOTE silent deactivation later removed upstream — open question in PR #448 |
| 20fd2e2 | fix: normalize calibration registry key to model id; revert cli.py helptext scope leak | upstream 099be3e same subject |
| 387ce5f | feat(simul): seed en→zh calibration (L9/H5 top, 8 heads, gate passed) | main has calibrations/translation_heads_..._en-zh.json |
| 0b1c5ea | fix(mlx-llm-mt): truncate at first Hunyuan placeholder at source | upstream fe220cc same subject |
| 95dda62 | feat(simul): port the mass commit policy from livecaption | upstream 01f0589 same subject; also exact patch in #425/#426 (38c6a0b) |
| 1fb6a73 | fix(simul): clear stale provisional buffer after emitting a final | behavior present in main _queue_final: clears _last_draft/_emitted_partial/_tail (adapted) |
| 25f2b78 | fix(simul): clear provisional buffer in validate_buffer_and_reset | behavior present in main _queue_final: clears _last_draft/_emitted_partial/_tail (adapted) |
| ccb6d64 | fix(mlx-llm-mt): address PR #422 reviewer blockers | #422 reviewer blockers, merged |
| 61c7668 | Merge branch 'spacedock-ensign/hunyuan-mlx-translation-backend' into feat/apple-silicon-backends | merge vehicle for the #422 hunyuan-mlx branch; content accounted in children |
| f5b2395 | fix(simul): add new_session override to MlxLlmTranslationSimul | upstream 57f18c4 same subject |
| bf383db | fix(simul): token-based hysteresis for MT draft calls (MIN_SOURCE_TOKENS) | in upstream 01f0589 (mass policy + token-hysteresis) |
| 38c6a0b | feat(simul): mass commit policy + token-hysteresis for mlx-llm-mt-simul | exact patch in origin/main AND #425/#426 |
| e6bda45 | feat(simul): seed en→zh and ja→zh calibration heads (8 heads each, L9/H5 top) | exact patch in origin/main AND #425/#426 |
| adbaefb | docs(simul): calibration heads guide — adding directions + fallback notice | exact patch in origin/main AND #425/#426 |
| f651c25 | fix(simul): thread commit_mode/mass_threshold through new_session | exact patch in origin/main AND #425/#426 |
| 65697f3 | Merge commit 'f651c25' into feat/apple-silicon-backends | sync merge of the simul branch; content accounted in children |
| 48da763 | feat(generation): endpointing owns segment closure — fragment finals and draft starvation fixed | upstream 67459c8 same subject (merged via #423) |
| 71041b4 | test(simul): endpointing contract tests — punct below soft_max holds, rule2/rule3 cut | endpointing contract tests inside upstream 67459c8 (test-name match verified by prior ensign) |
| ccb4090 | fix(simul): draft cache resets at segment close; stale tails dropped from the MT source | upstream 0e3e624 (the #423 port; patch differs by the audio_processor conflict resolution) |
| f67b3e1 | fix(simul): warm the simul draft path at init; require a fresh draft when the committed outgrows the cached span | exact patch in origin/main AND #425/#426 |
| 6e84067 | docs+chore: compaction survival notes — the commit policy deviates from the paper; simul head override env | code part upstream via c2dc34b (check_simul_heads.py + LC_SIMUL_HEAD); _work notes part local |
| c2e56dd | feat+docs: mlx-side TS calibration reproduces the PyTorch head ranking | upstream c3e3ee0 same subject (scripts/calibrate_ts_mlx.py is on main); _work notes stripped in port |
| fd49231 | test: deterministic record/replay fixture for the simul-MT translation subsystem | exact patch in origin/main AND #425/#426 |
| dda8aa1 | fix+feat: robust committed-frontier mapping + the paper's stabilized-argmax commit policy | exact patch in origin/main AND #425/#426 |
| fa20659 | feat: expose --simul-commit paper in lc_terminal | config part via upstream 5a8ef82; lc_terminal part rides with unique-client |
| 0598308 | feat: make the paper commit policy the default | upstream 0a6996f (config/core/engine default); lc_terminal line rides with unique-client |

## in-flight-PR (4)

| commit | subject | evidence |
|---|---|---|
| f1c24f9 | fix: normalize language tag before prompt_dictionary validation (AC-1) | #426: maintainer language handling d9143bb/7278e13; verify coverage at review |
| 52d9498 | feat: stack PR3 (mlx-qwen3-asr) onto nemotron tip (PR1+PR2+nemotron) | #425: merge brought the qwen3 backend; carried by e3a0862 lineage + follow-ups |
| bbb70c1 | fix(asr_commit): prefer native stable_text; CJK char-split + token-LCP fallback | exact patch in #425 and #426 |
| be0f4a1 | test: zh-ja fallback fixture checked in (no /tmp dependency) | #449: zh_ja_fallback.jsonl golden shipped |

## unique-simul-frontier (3)

| commit | subject | evidence |
|---|---|---|
| bcb0467 | feat(simul): opt-in time-based accessible frontier for the commit policy | the time-frontier stack; target = simul PR branch (next work item), re-verified vs the maintainer-adapted engine |
| 7f13e08 | fix(simul): end-of-feed clamp + released-prefix fragment guard for the time frontier | the time-frontier stack; target = simul PR branch (next work item), re-verified vs the maintainer-adapted engine |
| e9fbadf | feat(simul): auto resolves to the time frontier for every simul backend | the time-frontier stack; target = simul PR branch (next work item), re-verified vs the maintainer-adapted engine |

## unique-diarization (3)

| commit | subject | evidence |
|---|---|---|
| e735119 | feat(diarization): MLX-native sortformer backend (pure MLX, no NeMo) | MLX sortformer backend + contract fix + pyproject extra; port to upstream diarization/ package |
| c87e4ba | fix(diarization-mlx): match audio_processor contract (insert_audio_chunk/diarize) | MLX sortformer backend + contract fix + pyproject extra; port to upstream diarization/ package |
| f9b5768 | feat: add diarization-mlx-sortformer extra (mlx-audio for MLX diarization) | MLX sortformer backend + contract fix + pyproject extra; port to upstream diarization/ package |

## unique-client (29)

| commit | subject | evidence |
|---|---|---|
| 9fdff5d | fix(lc_terminal): clean startup (no fetch noise), ready signal, mic diag | lc_terminal fixes/diagnostics; file lives only here + wlk/tui-view lineage |
| 5178f81 | diag(lc_terminal): event-loop heartbeat + frequent chunk count | lc_terminal fixes/diagnostics; file lives only here + wlk/tui-view lineage |
| 58d74e1 | tui: provisional→final inline diff (struck gray old + bold green new) | TUI view styling; verify the diff styling was dropped per the 0dd1ec1 decision when TUI work resumes |
| de58da1 | fix(tui): 3-tuple segments + missing _last_prov init on TuiSink | TUI/overlay view fixes; carried in wlk/tui-view lineage |
| 1b9e65c | fix(overlay/lc_terminal): missing _field_en_prev init + MT sentence spacing | TUI/overlay view fixes; carried in wlk/tui-view lineage |
| 620ec2e | diag(lc_terminal): mic amplitude + device probe for silent-input diagnosis | lc_terminal fixes/diagnostics; file lives only here + wlk/tui-view lineage |
| 7307580 | fix(lc_terminal): clean Ctrl-C exit in terminal (non-overlay) mode | lc_terminal fixes/diagnostics; file lives only here + wlk/tui-view lineage |
| e0cafe9 | feat(lc_terminal): --nemotron-mlx-asr-model flag + tested-variant docs | lc_terminal flag |
| 57bafab | fix(overlay): dispatch AppKit UI updates to main thread + release lock during streaming | AppKit main-thread dispatch — view-side |
| 1e14933 | feat(overlay): restore the streaming word-by-word reveal effect | AppKit streaming/typing view behavior — view-side, lives on wlk/tui-view |
| 36f15b8 | fix(overlay): update _shown_en_plain incrementally during streaming | AppKit streaming/typing view behavior — view-side, lives on wlk/tui-view |
| 5bd7fee | diag(overlay): OV_DEBUG env var traces extends vs hard-swap in reconciler | AppKit streaming/typing view behavior — view-side, lives on wlk/tui-view |
| 5fbc514 | fix(overlay): stream every new caption word-by-word, not just extends | AppKit streaming/typing view behavior — view-side, lives on wlk/tui-view |
| 01b262e | fix(overlay): CJK-aware word-by-word streaming (pairs, not single chars) | AppKit streaming/typing view behavior — view-side, lives on wlk/tui-view |
| 37a5e25 | fix(overlay): don't re-trigger streaming toward the same target | AppKit streaming/typing view behavior — view-side, lives on wlk/tui-view |
| 3cc7e71 | fix(overlay): stream only on first appearance; hard-swap provisional→final | AppKit streaming/typing view behavior — view-side, lives on wlk/tui-view |
| 6d8e774 | feat: capture_overlay_events.py — event stream + frame-by-frame replay | capture_overlay_events.py tooling; #449 has the model-only replay instrument instead |
| d507667 | fix(overlay): hard-swap new captions, stream only on extends | AppKit streaming/typing view behavior — view-side, lives on wlk/tui-view |
| 2a77f47 | fix(lc_terminal): remove HF_HUB_OFFLINE=1 — blocks first-run model downloads | lc_terminal fixes/diagnostics; file lives only here + wlk/tui-view lineage |
| fa7350c | spike(caption-events): golden event player (TUI/overlay/plain) | view-level golden player (TUI/overlay/plain); view-side replay lives on wlk/tui-view |
| c0a0ec8 | fix(display): source reading buffer accumulates clauses; zh history promotes at sentence end; drop diff-green in the event path | src reading buffer (src_buffer.py on wlk/tui-view); no-diff-green decision embodied in #449 too |
| b47ee42 | fix(display): kill src-row flicker — single writer + change detection | src-row view rendering + reading buffer; view-side (src_buffer.py on wlk/tui-view) |
| 5f97cbb | fix(display): src row rendered by the drainer with change detection — kill ASR flicker | src-row view rendering + reading buffer; view-side (src_buffer.py on wlk/tui-view) |
| 321eaa1 | fix(display): src row attributed text carries the centered paragraph style | src-row view rendering + reading buffer; view-side (src_buffer.py on wlk/tui-view) |
| 2158805 | fix(display): FrontData finals pass incremental suffix to the reading buffer | src-row view rendering + reading buffer; view-side (src_buffer.py on wlk/tui-view) |
| 90b3712 | fix(display): terminal ASR lines print complete, not first-sight fragments | src-row view rendering + reading buffer; view-side (src_buffer.py on wlk/tui-view) |
| 25a7ac1 | fix(display): monotonic src display — hypothesis-revision shrinks are held | src-row view rendering + reading buffer; view-side (src_buffer.py on wlk/tui-view) |
| a3cff06 | fix(display): adaptive typing pace; src row expires on sustained silence | typing pace + src-row expiry — view behavior |
| f8c2ffd | fix: lc_terminal never exited after a normal file run | shutdown fix; lc_terminal is client-side |

## unique-eval (4)

| commit | subject | evidence |
|---|---|---|
| 2b781b9 | fix(simulst-eval): restore asr-mt mode (4 regressions since AC-1) | simulst-eval harness; adopt-upstream-FLEURS decision pending |
| d8912ee | feat(simulst-eval): wire nemotron-mlx backend into asr-mt emitter | simulst-eval harness; adopt-upstream-FLEURS decision pending |
| 0ec8077 | fix(simulst-eval): pace audio to realtime (honest live latency) | simulst-eval harness; adopt-upstream-FLEURS decision pending |
| 20607e5 | feat+docs: all-head mlx exploration — no head tracks the commit frontier; cadence is the bottleneck | explore_heads_mlx.py not upstream; scripts disposition task pending; _work notes local |

## local-custom (7)

| commit | subject | evidence |
|---|---|---|
| ddfff1e | feat: local-custom files (lc_terminal, overlay, tui, screen_ocr, eval harness, third_party) | origin commit of local tooling; final content distributed across client/eval commits |
| 55fa915 | feat: local-custom deltas (VAD knobs, --second-pass, overlay/opencc extras) | VAD knobs, --second-pass, overlay/opencc extras — captain-local preferences |
| 3f9446b | docs: compaction notes — deterministic fixture gate | internal _work notes; keep on the archived branch / state checkout |
| 687ad2b | docs: compaction notes — frontier mapping was the root cause; paper policy wired | internal _work notes; keep on the archived branch / state checkout |
| eaa37bc | docs: compaction notes — paper policy is the default | internal _work notes; keep on the archived branch / state checkout |
| fdc0ccc | docs: compaction notes — shutdown hang fix | internal _work notes; keep on the archived branch / state checkout |
| 5284a8b | docs: compaction notes — time-frontier A/B measured on zh and en clips | internal _work notes; keep on the archived branch / state checkout |

## superseded-display (35)

| commit | subject | evidence |
|---|---|---|
| 50f6b7c | overlay: model/view split — pure display state machine + thin AppKit view | #449 CaptionDisplay is the re-derived model/view split |
| 345d82c | fix(overlay_model): surface new translation/preview state immediately | #449 model surfaces state immediately (emission is push-based) |
| 53b399b | feat(overlay): port livecaption's overlay display delivery mechanism | delivery mechanism re-derived in #449 model |
| e6e400b | spike(caption-events): standardized event stream + display adapter + diff | #449 caption_events.py is the final form; ideal goldens shipped on #449 |
| fa4dcf9 | spike(caption-events): intuitive type names + compute flag | #449 caption_events.py is the final form; ideal goldens shipped on #449 |
| 18a4d3c | spike(caption-events): normalize provisional — ASR and MT both unfinalized | #449 caption_events.py is the final form; ideal goldens shipped on #449 |
| 5fee3ff | spike(caption-events): rename compute flag to fresh | #449 caption_events.py is the final form; ideal goldens shipped on #449 |
| 6159d6c | spike(caption-events): ideal event streams for zh->en and en->zh | #449 caption_events.py is the final form; ideal goldens shipped on #449 |
| 7f5fcb9 | spike(caption-events): rewrite goldens to obey the AlignAtt contract | #449 caption_events.py is the final form; ideal goldens shipped on #449 |
| 7c67775 | spike(caption-events): ideal-timeline goldens + per-sentence starvation scoring | ideal goldens shipped on #449; RESIDUAL: per-sentence starvation scoring not carried (event_diff removed in trim) — restore from here if wanted |
| 360755c | feat(caption-events): wire the caption event stream into the pipeline and display layer | #449 emission wiring (0143f1e-era, now 980ef9a) |
| eedb1b0 | fix(display): append effect for provisional growth — overlay model + TUI | append effect + queue survival semantics in #449 CaptionDisplay (tests pin) |
| 965aa6b | fix(display): append effect keyed on stream state, source line holds until new words | append effect + queue survival semantics in #449 CaptionDisplay (tests pin) |
| de40907 | fix(display): preempting final clears its own stale queued draft | append effect + queue survival semantics in #449 CaptionDisplay (tests pin) |
| 0dd1ec1 | fix(display): overlay shows only provisional-vs-committed, no diff coloring (CL) | no-diff-coloring embodied in #449 _segments_to_spans (del spans omitted) |
| 6d23623 | fix(display): src_join NameError crashed every commit — src buffer never accumulated | moot: the code it fixed was replaced by the #449 architecture |
| 0bb7062 | fix(golden): ASR provisionals grow with the speech, not pop-in whole clauses | #449 goldens are new recordings; old golden fixes superseded |
| 7d35684 | fix(display): promoted sentence suppressed from the tail — no re-appear as dim draft | promoted sentence not re-emitted as draft: #449 CaptionDisplay behavior (test pins) |
| d8d9428 | fix(golden): MT drafts arrive as the clause's words land, not at clause start | #449 goldens are new recordings; old golden fixes superseded |
| 8ca7074 | fix(display): cumulative line growth no longer swallows appended sentences; CJK detection fixed; src-row typing effect | model part (cumulative line growth) in #449; src-typing part is view (unique-client) |
| 2543a54 | fix(display): translation final flips dim→bright in place when the text is unchanged | #449 in-place dim->bright flip (tests) |
| e8d4e29 | fix(display): commit keeps the absorbed tail — no prefix flicker at mid-sentence commits | monotonic hold + amend semantics in #449 set_partial/model (tests pin) |
| 584c645 | fix(display): hold hypothesis rewording retractions, not just prefix shrinks | monotonic hold + amend semantics in #449 set_partial/model (tests pin) |
| 8c0950e | test: fix reword-hold expectation (the commit boundary resolves the hold) | monotonic hold + amend semantics in #449 set_partial/model (tests pin) |
| ce22a76 | fix(display): reworded longer provisional amends instead of hard-swapping | monotonic hold + amend semantics in #449 set_partial/model (tests pin) |
| ceec4e4 | fix(display): mid-sentence commits with a premature tail terminator still type | premature-terminator semantics: confirm a covering test exists in CaptionDisplay tests at PR review (old test file may not have carried the case) |
| c106c9c | test: premature-terminator test feeds delta commits (production semantics) | premature-terminator semantics: confirm a covering test exists in CaptionDisplay tests at PR review (old test file may not have carried the case) |
| 00b4c9b | fix(display): MT drafts release immediately — no more draft starvation behind finals | #449 draft release semantics |
| 94d217e | fix(display): drafts queue behind the final's hold again — finals never flash | #449 hold queue + min-hold (tests pin) |
| ca309ba | fix(display): fallback (no calibration) must not flash untranslated source as the MT draft; TUI renders from the event path | no-flash rule now STRUCTURAL in #449 (provides_drafts contract); TUI part view-side |
| 36061bd | fix(display): back-to-back finals queue instead of flashing; each holds a readable minimum | #449 hold queue + min-hold (tests pin) |
| 87a29f6 | test: consecutive-finals tests advance the clock past MIN_SHOW (the queue gate) | #449 hold queue + min-hold (tests pin) |
| 0bac199 | feat(overlay): sentence-partitioned caption display — commit over '.' queues the sentence | sentence partition + queue survival + in-place promotion carried by #449 (inside 9199cc5, tests pin) |
| 60285cb | fix(overlay): queued completed sentences survive drafts and queue-jumping finals | sentence partition + queue survival + in-place promotion carried by #449 (inside 9199cc5, tests pin) |
| b965d59 | fix(overlay): promote the typed sentence in place — no identical-content retype | sentence partition + queue survival + in-place promotion carried by #449 (inside 9199cc5, tests pin) |

## superseded-nemotron (5)

| commit | subject | evidence |
|---|---|---|
| 3f604b0 | feat: nemotron-mlx ASR transducer backend (pure MLX via mlx-audio) | #426 head rewrote asr_nemotron_mlx.py (-786/+140 vs integration); his 2f04c708 streaming-cache commit |
| 7a6cd09 | fix: nemotron default to mlx-community model, add qwen3-streaming/nemotron conflicts, uv environments, nemotron-mlx-asr backend choice in lc_terminal | maintainer 2f04c708 (compatible checkpoint) + his backend-choice/eval wiring |
| a632b1c | fix(nemotron-mlx): pin all MLX work to a single dedicated thread | maintainer 49e9017 "Keep Nemotron model loading and decoding on one MLX thread" |
| aa8b51a | feat(nemotron-mlx): time-based accessible boundary for AlignAtt simul-MT | superseded by the generic time frontier (unique-simul-frontier target, simul PR) |
| a130f4b | fix(nemotron-mlx): wire the loaded Silero VAD into the online processor | maintainer rewrite; verify VAD wiring present in his version at review |

## unsure (3)

| commit | subject | evidence |
|---|---|---|
| e9956a0 | feat(simul): seed ja→zh calibration (L9/H5 top, 8 heads, gate passed) | ja→zh seed; NOT in main (only en-zh). Captain already dropped ja→zh from #448 (thin corpus) — confirm permanent drop |
| bf789a7 | fix(audio-processor): silent-backend watchdog is speech-aware | never merged (integration-only); assign a home: qwen3 PR or standalone fix; note it caused a test-fixture mismatch on the display branch |
| b833489 | fix(profiles): add dot-form aliases for hy-mt2 model ids | dot-form model-id normalization VERIFIED ABSENT from main (translation_profiles + simul_mt_capture have no dot normalize); small standalone fix — assign a home: ride with the simul PR or standalone |

## Carve-out notes for the next step

- **unique-simul-frontier (3)**: `bcb0467`, `7f13e08`, `e9fbadf` — port onto origin/main's maintainer-adapted simul engine, stacked on #448 (zh→en calibration required to construct the engine). Gate-semantics decision folds into the PR body.
- **unique-diarization (3)**: `e735119`, `c87e4ba`, `f9b5768` — port onto origin/main's `diarization/` package structure.
- **unique-client (29)**: lc_terminal.py, the TUI/overlay views and their fixes, the view-level replay tooling. `wlk/tui-view` already carries tui.py + overlay.py + src_buffer.py from the f8110c9 lineage; at carve-out, diff the integration branch's final `lc_terminal.py`/`tui.py`/`overlay.py` against wlk/tui-view's copies to catch client fixes that postdate that port (notably `f8c2ffd`, `2a77f47`, `e0cafe9`, and the src-row series).
- **unique-eval (4)**: simulst-eval harness + explore_heads_mlx.py. Decision pending: adopt upstream's FLEURS harness instead; if so these stay on the archived branch only.
- **local-custom (7)**: captain-local files and internal `_work/` notes. Never PR'd; keep on the archived branch or copy into the state checkout.
- **unsure (3)**: `e9956a0` (ja→zh seed — captain already dropped ja→zh from #448; confirm permanent drop), `bf789a7` (silent-backend watchdog — assign a home), `b833489` (dot-form model-id normalization — verified absent from main; assign a home).

## Retirement rule

A commit is safe to lose at branch retirement iff it is merged-upstream, in-flight-PR, superseded-display, or superseded-nemotron. Everything else must first live on a named branch or in the state checkout. By the counts above: 72 commits are safe today (28 merged-upstream + 4 in-flight-PR + 35 superseded-display + 5 superseded-nemotron); 49 (39 unique-* + 7 local-custom + 3 unsure) still need a home or an explicit drop decision.

