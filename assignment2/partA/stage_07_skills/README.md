# Stage 07 — Skills

**The idea:** don't pay for instructions the model isn't using. A skill is
a folder with a `SKILL.md`: YAML front matter (`name`, `description`) plus
a body of free-form instructions. Only the front matter goes into the
system prompt, every turn, for every skill. The body loads on demand, via
a `read_skill` tool call, only when the model decides it's relevant.

## Run it

```powershell
.venv\Scripts\python.exe stage_07_skills\main.py
```

Try: *"write me a commit message for this change"* or *"explain what
tools.py does"* — watch it call `read_skill` before answering.

## Layout

```
stage_07_skills/
  skills/
    explain_code/SKILL.md
    commit_message/SKILL.md
  skills.py
  tools.py
  ui.py
  main.py
```

## The code

`skills/*/SKILL.md` looks like this:

```markdown
---
name: commit_message
description: Use this when the user asks for a git commit message, or asks you to commit a change.
---

# Commit Message

Write commit messages in this shape:
1. First line: a short imperative summary, under 70 characters...
```

`skills.py` parses that front matter with `pyyaml` and keeps the body as
plain text:

```python
def skills_system_prompt():
    lines = ["Available skills. Call read_skill(name) to load one's full instructions:"]
    for name, info in SKILLS.items():
        lines.append(f"- {name}: {info['description']}")
    return "\n".join(lines)
```

This function is the entire "menu" the model sees on every single request
— two short lines per skill. Compare that to what `read_skill` returns:

```python
def read_skill(name: str) -> str:
    skill = SKILLS.get(name)
    ...
    return skill["body"]
```

The full body (which could be hundreds of lines — checklists, examples,
edge cases) only crosses the wire the turn the model actually asks for it.
Ten skills cost ten menu lines whether zero or all ten get used; a skill's
real cost only shows up once it's loaded.

### Only two lines changed in main.py

```python
system_prompt = skills_system_prompt()
if system_prompt:
    messages.append({"role": "system", "content": system_prompt})
```

`read_skill` itself is just another entry in `tools.py`'s registry — the
loop in `main.py` doesn't know skills exist as a concept; it dispatches
`read_skill` exactly like `bash` or `read_file`.

## Diff

```powershell
git diff --no-index stage_06_chat_ui stage_07_skills
```
