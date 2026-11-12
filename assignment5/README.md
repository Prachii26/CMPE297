# Assignment 5 — Three October-2026 RSI methods on one NL2SQL task

**Demo video:** YOUTUBE_VIDEO_LINK

*Work in progress — the comparison table and per-method results are filled in as each method is verified.*

| Method | Status |
|---|---|
| task/ | done — 120 questions, starting solver 25.0% on every split |
| guard/ | done — 18 tests; fired on real proposals in every method so far, including the gutted-solver check |
| 00_baseline | done — held-out 0.250 → 0.520 ± 0.154 (scripted, 5 seeds); 0.250 → 0.575 (live gemini-3.5-flash, 8 calls) |
| 01_so_rsi | done — held-out 0.520 → 0.940 ± 0.108 vs baseline, same seeds and budget; blind repeats 2.2 → 0, oscillations 1.0 → 0 (scripted, 5 seeds) |
| 02_dream_rsi | pending |
| 03_aide2 | pending |
