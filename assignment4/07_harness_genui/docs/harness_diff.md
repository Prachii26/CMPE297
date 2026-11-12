# What changed in my stage 15 harness

Source: [`assignment2/partA/stage_15_subagents`](../../../assignment2/partA/stage_15_subagents/) at commit `5aafb54`, copied into `07_harness_genui/harness/`.

## Files compared byte for byte

| file | status |
|---|---|
| `README.md` | unchanged |
| `compaction.py` | unchanged |
| `context.py` | unchanged |
| `main.py` | **modified** (diff below) |
| `permissions.py` | unchanged |
| `sandbox.py` | unchanged |
| `sessions.py` | unchanged |
| `skills.py` | unchanged |
| `subagent.py` | unchanged |
| `todos.py` | unchanged |
| `tools.py` | unchanged |
| `ui.py` | unchanged |
| `render_ui.py` | **new** in assignment 4 |
| `terminal_surface.py` | **new** in assignment 4 |
| `scripted_client.py` | **new** in assignment 4 |
| `data.py` | **new** in assignment 4 |

`skills/` copied unchanged.

## The diff of main.py

```diff
@@ -1,4 +1,12 @@
-"""Stage 15: subagents.
+"""Stage 15: subagents -- extended in assignment 4 with a render_ui tool.
+
+[A4] marks every line assignment 4 added; everything else is stage 15 as
+written in assignment 2. Additions: the render_ui tool (render_ui.py), two
+surfaces for it (terminal_surface.py, and the browser via ../server.py with
+--web), a --mode flag for the four generation modes, and a scripted client
+(scripted_client.py) used instead of OpenRouter unless HARNESS_SCRIPTED=0.
+
+Stage 15: subagents.
 
 One addition to stage 14's registry: ALL_TOOLS / ALL_FUNCTIONS layer the
 `task` tool (from subagent.py) on top of the base registry from tools.py.
@@ -21,6 +29,10 @@ from sessions import latest_session_id, load_messages, log_message, log_rewind,
 from skills import skills_system_prompt
 from subagent import TASK_SCHEMA, task
 from tools import FUNCTIONS, TOOLS
+import render_ui as genui                                          # [A4]
+from render_ui import RENDER_UI_SCHEMA, render_ui                  # [A4]
+from scripted_client import ScriptedClient                         # [A4]
+from terminal_surface import TerminalSurface                       # [A4]
 
 load_dotenv(find_dotenv())
 
@@ -32,11 +44,13 @@ MAX_TURNS = 10
 # by task() get tools.TOOLS/FUNCTIONS filtered down (see subagent.py) --
 # this is the one place `task` itself is added back in, for the top level
 # only, since subagent.py deliberately withholds it.
-ALL_TOOLS = TOOLS + [TASK_SCHEMA]
-ALL_FUNCTIONS = {**FUNCTIONS, "task": task}
+ALL_TOOLS = TOOLS + [TASK_SCHEMA, RENDER_UI_SCHEMA]                # [A4] + render_ui
+ALL_FUNCTIONS = {**FUNCTIONS, "task": task, "render_ui": render_ui}  # [A4] + render_ui
 
 
 def make_client():
+    if os.environ.get("HARNESS_SCRIPTED", "1") == "1":            # [A4] offline, no key
+        return ScriptedClient()                                    # [A4]
     return OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY", ""), base_url=BASE_URL)
 
 
@@ -115,9 +129,28 @@ def handle_slash_command(command, session_id, messages):
         ui.print_system(f"unknown command: {command}")
 
 
+def _flag(argv, name, default=None):                               # [A4]
+    return argv[argv.index(name) + 1] if name in argv else default  # [A4]
+
+
+def run_turn(client, messages, session_id, user_input):            # [A4] one turn, shared by
+    genui.CURRENT_REQUEST = user_input                             # [A4] the REPL, --prompt
+    user_msg = {"role": "user", "content": user_input}             # [A4] and web actions
+    messages.append(user_msg)                                      # [A4]
+    log_message(session_id, user_msg)                              # [A4]
+    reply = run_loop(client, messages, session_id)                 # [A4]
+    assistant_msg = {"role": "assistant", "content": reply}        # [A4]
+    messages.append(assistant_msg)                                 # [A4]
+    log_message(session_id, assistant_msg)                         # [A4]
+    ui.print_reply(reply)                                          # [A4]
+    return reply                                                   # [A4]
+
+
 def main(argv=None):
     argv = sys.argv[1:] if argv is None else argv
     resume = "--resume" in argv
+    genui.MODE = _flag(argv, "--mode", "declarative")              # [A4]
+    genui.SURFACES[:] = [TerminalSurface()]                        # [A4]
 
     if resume:
         session_id = latest_session_id()
@@ -131,7 +164,12 @@ def main(argv=None):
         messages = []
 
     client = make_client()
-    ui.banner(MODEL, sandbox_status())
+    if "--web" in argv:                                            # [A4] second surface
+        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # [A4]
+        import server                                              # [A4]
+        server.attach(lambda text: run_turn(client, messages, session_id, text),  # [A4]
+                      port=int(_flag(argv, "--port", "8007")))     # [A4]
+    ui.banner(MODEL if not isinstance(client, ScriptedClient) else "scripted (offline)", sandbox_status())  # [A4]
     if resume and messages:
         ui.print_system(f"resumed session {session_id} ({len(messages)} messages)")
     else:
@@ -144,6 +182,13 @@ def main(argv=None):
             messages.append(sys_msg)
             log_message(session_id, sys_msg)
 
+    if "--prompt" in argv:                                         # [A4] non-interactive turn
+        run_turn(client, messages, session_id, _flag(argv, "--prompt"))  # [A4]
+        if "--web" not in argv:                                    # [A4]
+            return messages                                        # [A4]
+        server.serve_forever()                                     # [A4]
+        return messages                                            # [A4]
+
     while True:
         try:
             user_input = ui.get_input()
@@ -157,15 +202,7 @@ def main(argv=None):
             handle_slash_command(user_input.strip(), session_id, messages)
             continue
 
-        user_msg = {"role": "user", "content": user_input}
-        messages.append(user_msg)
-        log_message(session_id, user_msg)
-
-        reply = run_loop(client, messages, session_id)
-        assistant_msg = {"role": "assistant", "content": reply}
-        messages.append(assistant_msg)
-        log_message(session_id, assistant_msg)
-        ui.print_reply(reply)
+        run_turn(client, messages, session_id, user_input)         # [A4] (same steps as before)
 
 
 if __name__ == "__main__":
```
