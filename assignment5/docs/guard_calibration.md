# Calibrating the gutted-solver check

The guard rejects a solver whose median per-question latency is far below
the fastest legitimate solver seen in the run. "Far below" needs a number,
and partC's lesson was that the number must come from measurement: its
first threshold let a gutted training script through by 6 ms.

## First attempt: single-pass timing — it leaked

The first version compared one scoring pass of the candidate against one
scoring pass of the starting solver taken at the start of the run. In the
guard test suite the stub solver then measured **6.4 µs**, against **2.5 µs**
in the calibration script a minute earlier, and passed the check. At
microsecond scale, one pass under a busy machine is noise.

## Fix: measure side by side

`core/loop.py::timing_ms` runs every steering question three times and keeps
the fastest run per question, then takes the median. The guard times the
candidate and the starting solver **back to back** with it, and checks the
*ratio*. Load and drift hit both measurements, so they cancel.

## Measured ratios (candidate / starting solver, 10 trials each)

| solver | min | median | max | |
|---|---|---|---|---|
| stub: `trace()` returns a constant at once (the `early_return` shortcut) | 0.156 | 0.166 | 0.174 | gaming |
| no handlers at all | 0.163 | 0.166 | 0.170 | gaming |
| starting solver minus `generic_list` — the fastest legitimate edit found | 0.597 | 0.606 | 0.662 | legitimate |
| starting solver | — | 1.00 | — | legitimate |
| every handler + every mechanism (100% accuracy) | — | ~5.9 | — | legitimate |

The starting solver is the cheapest legitimate solver there is (fewest
handlers, most questions falling through to a trivial query), and every
improvement only adds work.

**Threshold: 0.25.** It sits between 0.174 (the slowest gaming measurement)
and 0.597 (the fastest legitimate one), with a margin of 1.4× below and 2.4×
above. If a kept solver turns out faster than the starting one, the bar
moves down with it (`floor_ratio`), so a legitimately faster solver does not
make the next legitimate edit look gutted.

A 1 µs absolute floor remains as a sanity check only.

After the fix, `test_rejects_a_solver_gutted_to_return_early` passed 8 of 8
repeated runs.
