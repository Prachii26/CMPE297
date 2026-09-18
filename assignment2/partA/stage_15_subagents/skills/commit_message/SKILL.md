---
name: commit_message
description: Use this when the user asks for a git commit message, or asks you to commit a change.
---

# Commit Message

Write commit messages in this shape:

1. First line: a short imperative summary, under 70 characters, no
   trailing period. ("Add retry logic to bash tool", not "Added..." or
   "Adds...").
2. Blank line.
3. Body (optional, only if the "why" isn't obvious from the summary):
   1-3 sentences on why the change was made, not what it does line by
   line -- the diff already shows what changed.
4. Never invent a scope, ticket number, or co-author line the user didn't
   provide.

If the user hasn't shown you the diff yet, ask to see it (or run
`git diff`) before writing the message -- don't guess at what changed.
