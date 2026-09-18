# Prompt used to build this

This is the exact text from the assignment that specified Part C,
quoted verbatim, across the two messages that shaped it:

## Initial build prompt

> Part C. Build a custom ML harness plugin for autoresearch, end to end.
> Work in Assignment2/partC/.
>
> The assignment marks this part IMPORTANT, so it gets the most care.
>
> ## What autoresearch is
> Karpathy's pattern: a program.md instructs a coding agent to edit one
> target file, run it against an evaluation metric under a fixed time
> budget, then keep the change if the metric improved or revert it if it
> did not, and loop. The structure is portable to any optimizable target.
>
> ## What to build
> A DSH plugin called "autoresearch" that runs this loop end to end on a
> real ML task.
>
> Components:
> 1. A target: train.py, a small ML training script that runs in under
>    60 seconds on CPU. Use a synthetic or sklearn built-in dataset -- no
>    downloads, no GPU, no API keys. The metric must be genuinely
>    improvable, not already maxed out.
> 2. A held-out evaluation the optimizer cannot see or touch. This is
>    the whole game -- if the loop can tune against the eval set, the
>    numbers are meaningless. Enforce the separation in code and say how
>    in the README.
> 3. The loop itself, as a DSH plugin: propose an edit, run, measure,
>    keep or revert, log the attempt, repeat for N iterations.
> 4. A run ledger: every iteration recorded with what changed, the
>    metric before and after, the decision, and elapsed time.
>    Append-only, JSON.
> 5. A reward-hacking guard. This is the part that separates a real
>    autoresearch harness from a toy. Detect and reject: edits that
>    touch the eval code or the held-out split, edits that hardcode or
>    memorize expected outputs, edits that change the metric definition
>    itself, runs that finish suspiciously fast. Log every rejection with
>    its reason.
> 6. A results view: iteration history, metric trajectory, accept/reject
>    counts, best-so-far.
>
> ## Requirements
> - It must actually run and produce a real improvement trajectory. Run
>   it for at least 10 iterations and show me the ledger.
> - Honest reporting. If the loop plateaus or regresses, the README says
>   so. A flat trajectory reported honestly beats a fabricated climb.
> - Follow the DSH plugin structure from the Part B docs work, and use
>   the Cordis API as it actually is, not as you expect it to be.
> - README covering: what autoresearch is, how this implementation
>   works, the leakage boundary, the reward-hacking guards and what each
>   prevents, how to run it, and the actual results from the 10-iteration
>   run.
> - Save the prompt used to build this.
>
> Start by writing train.py and confirming it runs and produces a
> baseline metric. Show me that baseline before building the loop
> around it.

## Follow-up prompt, after the baseline was shown and approved

> Baseline approved. Build the loop.
>
> One addition: log the wall-clock time of every iteration in the
> ledger and flag any run that finishes significantly faster than
> baseline. A run that skips actual training is one of the ways this
> loop gets gamed, and 0.016s is a low enough bar that a hollowed-out
> train.py would be obvious.
>
> Also make sure the ledger records the reason for every revert, not
> just that one happened. The rejection log is the interesting artifact
> here -- more so than the accepted edits.
>
> Run it for at least 10 iterations and show me the ledger when it's
> done.

## What actually shaped the implementation beyond that text

- **The baseline was built and run first, standalone**, before any
  plugin code existed, exactly as asked: `harness/data.py` (the fixed
  train/held-out split), `target/train.py` (a deliberately weak
  `DecisionTreeClassifier(max_depth=2)`), and `harness/evaluate.py` (the
  held-out scorer) were written and run manually, producing the
  67.11% baseline shown to the user before the loop was designed.
- **`ctx.llm.stream()`'s real message shape was checked against the
  running instance, not assumed.** The first boot attempt failed with
  `ERR_MODULE_NOT_FOUND: Cannot find package '@deepseek-ai/dsh-llm'`,
  because this plugin is loaded locally by absolute path
  (`custom-plugins.patch.yml`), not installed through pnpm, so it sits
  outside the profile's own dependency graph and cannot `import` a
  helper from that package. Fixed by constructing the message as a
  plain `{ role: 'user', content: [...] }` object instead of importing
  `createUserMessage` -- confirmed working against the live dsh
  instance, following this same conversation's instruction from Part B
  to "use the Cordis API as it actually is."
- **The timing guard's exact threshold came from a measured number, not
  a guess.** `harness/runner.js` was tested standalone against the real
  baseline before being wired into the loop, which is what produced the
  concrete "~2.9-3.7s baseline subprocess wall-clock" figure the
  timing guard's `MIN_FRACTION_OF_BASELINE` is calibrated against.
