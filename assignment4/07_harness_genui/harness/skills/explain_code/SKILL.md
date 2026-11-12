---
name: explain_code
description: Use this when the user asks you to explain what a piece of code does, how it works, or to walk through a file.
---

# Explain Code

Follow this order when explaining code to the user:

1. Read the relevant file(s) first with `read_file`. Never guess at
   contents you haven't read.
2. State the purpose in one sentence before diving into any detail.
3. Walk through the logic in the order it *executes*, not the order it's
   *defined* in the file (e.g. explain `main()`'s call order, not top to
   bottom of the file).
4. Call out anything non-obvious: side effects, mutation of shared state,
   error handling, or a subtle invariant a reader could miss.
5. Keep it shorter than the code itself. Do not restate every line -- only
   the lines that would confuse someone reading it cold.
