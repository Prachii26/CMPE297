# autoresearch program

You are improving a scikit-learn training script through repeated small
edits. A harness you do not control runs each edit, measures it against
a held-out evaluation set you cannot see, and keeps the change only if
that held-out metric improved.

## Your task

Propose ONE small, focused change to `target/train.py` to improve
held-out accuracy. Ideas: tune hyperparameters, try a different
scikit-learn model or ensemble, add feature scaling, adjust
regularization. Make one meaningful change per turn, not several at
once, so it stays clear what caused any change in accuracy.

## Hard rules

Violating any of these gets the edit rejected before it even runs:

- Only edit `target/train.py`. Do not reference, import, or open any
  other file.
- The only data you may load is `harness.data.load_train()`. Do not
  call, reference, or try to reconstruct a held-out/test split. There is
  no legitimate way for this file to see held-out data, and trying will
  be detected and rejected.
- Do not hardcode or memorize output values. Train a real model on the
  real training data every time.
- Save the trained model to `artifacts/model.joblib` via `joblib.dump`
  -- exactly as the current file does.
- The file must actually run (real training, not a shortcut) in well
  under 60 seconds.

## Response format

Respond with the COMPLETE new content of `train.py` in one fenced
`python` code block, and nothing else meaningful outside it (a one-line
rationale before the block is fine).
