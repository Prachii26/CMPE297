"""Runs every stage against a fake model. No API key required.

Each stage module is loaded fresh from its own directory, its `make_client`
(or equivalent client factory) is monkeypatched to return a FakeClient
that plays back a scripted list of responses, and the stage's own main()
or run loop is exercised exactly as a real user would trigger it.

Usage:
    .venv\\Scripts\\python.exe run_tests.py
"""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Fake model plumbing shared by every stage test.
# ---------------------------------------------------------------------------


def fake_usage(prompt=10, completion=5, cached=None, cost=None):
    details = SimpleNamespace(cached_tokens=cached) if cached is not None else None
    usage = SimpleNamespace(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        prompt_tokens_details=details,
    )
    if cost is not None:
        usage.cost = cost
    return usage


def fake_tool_call(call_id, name, arguments_json):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments_json),
    )


def fake_response(content=None, tool_calls=None, usage=None):
    message = SimpleNamespace(role="assistant", content=content, tool_calls=tool_calls)
    finish_reason = "tool_calls" if tool_calls else "stop"
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], usage=usage or fake_usage())


class FakeCompletions:
    """Stands in for client.chat.completions. Plays back a scripted list."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("fake model ran out of scripted responses")
        next_item = self.script.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        if callable(next_item) and not isinstance(next_item, SimpleNamespace):
            return next_item(kwargs)
        return next_item


class FakeChat:
    def __init__(self, script):
        self.completions = FakeCompletions(script)


class FakeClient:
    """Stands in for the OpenAI client. Only .chat.completions.create is used
    anywhere in this codebase, so that is all a fake needs to provide."""

    def __init__(self, script):
        self.chat = FakeChat(script)


def load_module(stage_dir, entry_filename, mod_name="stage_under_test"):
    """Import a stage's entry file fresh, with its own directory on sys.path
    so its sibling imports (tools, ui, ...) resolve to ITS files, not a
    same-named module cached from a previously tested stage."""
    dir_path = ROOT / stage_dir
    for py_file in dir_path.glob("*.py"):
        sys.modules.pop(py_file.stem, None)
    sys.modules.pop(mod_name, None)
    sys.path.insert(0, str(dir_path))
    try:
        spec = importlib.util.spec_from_file_location(mod_name, dir_path / entry_filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(dir_path))
    return module


@contextlib.contextmanager
def captured_stdout():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf


# ---------------------------------------------------------------------------
# Per-stage tests. Each raises AssertionError on failure.
# ---------------------------------------------------------------------------


def test_stage_01():
    mod = load_module("stage_01_minimal_chat", "chat.py")
    script = [fake_response(content="Hello there, friend, good day!", usage=fake_usage(cached=4))]
    mod.make_client = lambda: FakeClient(script)
    with captured_stdout() as out:
        mod.main()
    text = out.getvalue()
    assert "reply: Hello there, friend, good day!" in text
    assert "cached_tokens=4" in text


def test_stage_02():
    mod = load_module("stage_02_bash_tool", "chat.py")
    tool_call = fake_tool_call("call_1", "bash", '{"command": "echo hi"}')
    script = [fake_response(tool_calls=[tool_call])]
    mod.make_client = lambda: FakeClient(script)
    with captured_stdout() as out:
        mod.main()
    text = out.getvalue()
    assert "model called: bash" in text
    assert "hi" in text  # the real bash() ran "echo hi" against the real shell


def test_stage_03():
    mod = load_module("stage_03_tool_registry", "main.py")
    tool_call = fake_tool_call("call_1", "bash", '{"command": "echo hi"}')
    script = [fake_response(tool_calls=[tool_call])]
    mod.make_client = lambda: FakeClient(script)
    with captured_stdout() as out:
        mod.main()
    text = out.getvalue()
    assert "model called: bash" in text
    assert "hi" in text


def test_stage_04():
    mod = load_module("stage_04_read_file", "main.py")
    target = ROOT / "stage_04_read_file" / "tools.py"
    tool_call = fake_tool_call("call_1", "read_file", json.dumps({"path": str(target)}))
    script = [fake_response(tool_calls=[tool_call])]
    mod.make_client = lambda: FakeClient(script)
    with captured_stdout() as out:
        mod.main()
    text = out.getvalue()
    assert "model called: read_file" in text
    assert "def read_file" in text  # the tool printed its own source file's contents


def test_stage_05():
    mod = load_module("stage_05_agent_loop", "main.py")
    target = ROOT / "stage_05_agent_loop" / "tools.py"
    tool_call = fake_tool_call("call_1", "read_file", json.dumps({"path": str(target)}))
    script = [
        fake_response(tool_calls=[tool_call]),
        fake_response(content="There are 2 tools registered: bash and read_file."),
    ]
    client = FakeClient(script)
    mod.make_client = lambda: client
    with captured_stdout() as out:
        mod.main()
    text = out.getvalue()
    assert "reply: There are 2 tools registered" in text
    # the loop must have made exactly 2 requests: one that got the tool
    # call, one that got the final text answer
    assert len(client.chat.completions.calls) == 2
    # and the 2nd request must carry the assistant tool_calls message AND
    # a tool-role message tagged with the matching tool_call_id
    second_request_messages = client.chat.completions.calls[1]["messages"]
    roles = [m["role"] for m in second_request_messages]
    assert "assistant" in roles and "tool" in roles
    tool_msg = next(m for m in second_request_messages if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "call_1"


def test_stage_06():
    mod = load_module("stage_06_chat_ui", "main.py")
    tool_call = fake_tool_call("call_1", "bash", '{"command": "echo hi"}')
    script = [
        fake_response(tool_calls=[tool_call]),
        fake_response(content="Done: hi"),
    ]
    client = FakeClient(script)
    mod.make_client = lambda: client

    inputs = iter(["run echo hi and tell me the output"])

    def fake_get_input():
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError  # outer loop's exit condition, same as real Ctrl+D

    mod.ui.get_input = fake_get_input

    with captured_stdout() as out:
        mod.main()
    text = out.getvalue()
    assert "model: " in text  # banner printed via ui.py
    assert "usage:" in text  # printed after every call, not just at the end
    assert "Done: hi" in text


def test_stage_07():
    mod = load_module("stage_07_skills", "main.py")
    tool_call = fake_tool_call("call_1", "read_skill", '{"name": "commit_message"}')
    script = [
        fake_response(tool_calls=[tool_call]),
        fake_response(content="Sure, here's a commit message: ..."),
    ]
    client = FakeClient(script)
    mod.make_client = lambda: client

    inputs = iter(["write me a commit message"])

    def fake_get_input():
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    mod.ui.get_input = fake_get_input

    with captured_stdout() as out:
        mod.main()
    text = out.getvalue()
    assert "commit message: ..." in text

    # the system prompt (sent as the first request's messages) must carry
    # only name + description for both example skills, never the body text
    first_request_messages = client.chat.completions.calls[0]["messages"]
    system_msg = next(m for m in first_request_messages if m["role"] == "system")
    assert "explain_code" in system_msg["content"]
    assert "commit_message" in system_msg["content"]
    assert "Never invent a scope" not in system_msg["content"]  # that's body text, must stay out


def test_stage_08():
    # Unit-test str_replace directly first: this is the logic the assignment
    # cares about, and it's easiest to pin down precisely outside a full loop.
    mod = load_module("stage_08_file_editing", "tools.py", mod_name="stage08_tools")
    scratch = ROOT / "_scratch_stage_08.txt"
    scratch.write_text("alpha beta alpha", encoding="utf-8")
    try:
        zero_match = mod.str_replace(str(scratch), "gamma", "delta")
        assert zero_match.startswith("error:") and "not found" in zero_match

        many_match = mod.str_replace(str(scratch), "alpha", "delta")
        assert many_match.startswith("error:") and "matches 2 times" in many_match

        # file must be untouched after both refusals
        assert scratch.read_text(encoding="utf-8") == "alpha beta alpha"

        ok = mod.str_replace(str(scratch), "beta", "GAMMA")
        assert ok == f"replaced 1 match in {scratch}"
        assert scratch.read_text(encoding="utf-8") == "alpha GAMMA alpha"
    finally:
        scratch.unlink(missing_ok=True)

    # Then a full-loop smoke test: the model tries a bad str_replace, sees
    # the refusal as a tool result, and gets a final answer through main.py.
    main_mod = load_module("stage_08_file_editing", "main.py")
    target = ROOT / "_scratch_stage_08b.txt"
    target.write_text("one two three", encoding="utf-8")
    try:
        bad_call = fake_tool_call(
            "call_1", "str_replace",
            json.dumps({"path": str(target), "old_str": "nope", "new_str": "x"}),
        )
        script = [
            fake_response(tool_calls=[bad_call]),
            fake_response(content="That text wasn't found, so I made no changes."),
        ]
        client = FakeClient(script)
        main_mod.make_client = lambda: client
        inputs = iter(["replace nope with x"])

        def fake_get_input():
            try:
                return next(inputs)
            except StopIteration:
                raise EOFError

        main_mod.ui.get_input = fake_get_input
        with captured_stdout() as out:
            main_mod.main()
        text = out.getvalue()
        assert "wasn't found" in text
        # the refusal must have gone back to the model as a tool result,
        # not raised as an exception that would have killed the loop
        second_request = client.chat.completions.calls[1]["messages"]
        tool_msg = next(m for m in second_request if m["role"] == "tool")
        assert "not found" in tool_msg["content"]
    finally:
        target.unlink(missing_ok=True)


def test_stage_09():
    mod = load_module("stage_09_late_injection", "main.py")
    tool_call = fake_tool_call("call_1", "bash", '{"command": "echo hi"}')
    script = [
        fake_response(tool_calls=[tool_call]),
        fake_response(content="ok"),
    ]
    client = FakeClient(script)
    mod.make_client = lambda: client
    inputs = iter(["what time is it"])

    def fake_get_input():
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    mod.ui.get_input = fake_get_input
    with captured_stdout() as out:
        mod.main()

    calls = client.chat.completions.calls
    assert len(calls) == 2
    for call in calls:
        reminders = [m for m in call["messages"] if "<system-reminder>" in (m["content"] or "")]
        # exactly one reminder per outgoing request. If the reminder had
        # ever been appended to the persisted `messages` list instead of
        # spliced in per-call, call 2 would carry TWO of them (one stale,
        # one fresh) since it reuses call 1's growing transcript.
        assert len(reminders) == 1


def test_stage_10():
    mod = load_module("stage_10_sessions", "main.py")
    sessions_mod = sys.modules["sessions"]

    with tempfile.TemporaryDirectory() as tmp:
        sessions_mod.SESSIONS_DIR = Path(tmp)

        # Run 1: a plain exchange, no tools.
        client1 = FakeClient([fake_response(content="hi there")])
        mod.make_client = lambda: client1
        inputs1 = iter(["hello"])

        def get_input_1():
            try:
                return next(inputs1)
            except StopIteration:
                raise EOFError

        mod.ui.get_input = get_input_1
        with captured_stdout() as out1:
            mod.main(argv=[])
        assert "hi there" in out1.getvalue()

        session_files = list(Path(tmp).glob("*.jsonl"))
        assert len(session_files) == 1
        events = [json.loads(l) for l in session_files[0].read_text(encoding="utf-8").splitlines()]
        assert events[0]["type"] == "message" and events[0]["message"]["role"] == "system"
        assert any(e["message"]["role"] == "user" for e in events if e["type"] == "message")
        assert any(e["message"]["role"] == "assistant" for e in events if e["type"] == "message")

        # Run 2: --resume reopens that same session, then /rewind.
        client2 = FakeClient([fake_response(content="second reply")])
        mod.make_client = lambda: client2
        inputs2 = iter(["another message", "/rewind"])

        def get_input_2():
            try:
                return next(inputs2)
            except StopIteration:
                raise EOFError

        mod.ui.get_input = get_input_2
        with captured_stdout() as out2:
            mod.main(argv=["--resume"])
        text2 = out2.getvalue()
        assert "resumed session" in text2
        assert "second reply" in text2
        assert "rewound" in text2
        # /rewind is a slash command: it must NOT have reached the model.
        assert len(client2.chat.completions.calls) == 1
        # --resume appends to the existing file, it does not start a new one.
        assert len(list(Path(tmp).glob("*.jsonl"))) == 1

        # The rewind marker must actually take effect on the next replay:
        # "another message" (and its reply) should be gone from the
        # effective transcript, even though the raw JSONL still has them.
        loaded = sessions_mod.load_messages(session_files[0].stem)
        assert not any(m.get("content") == "another message" for m in loaded)
        raw_line_count = len(session_files[0].read_text(encoding="utf-8").splitlines())
        assert raw_line_count > len(loaded)  # rewind marker + cut messages still on disk


def test_stage_11():
    mod = load_module("stage_11_todos", "main.py")
    todos_mod = sys.modules["todos"]
    sessions_mod = sys.modules["sessions"]

    # Unit-test the validation rule directly: it's the crux of this stage.
    bad = todos_mod.write_todos(
        [
            {"content": "a", "status": "pending"},
            {"content": "b", "status": "in_progress"},
            {"content": "c", "status": "in_progress"},
        ]
    )
    assert bad.startswith("error:") and "exactly one" in bad
    assert todos_mod.TODOS == []  # a rejected write must not mutate state

    ok = todos_mod.write_todos(
        [{"content": "a", "status": "pending"}, {"content": "b", "status": "in_progress"}]
    )
    assert ok == "todo list updated, 2 item(s)"
    todos_mod.TODOS = []  # reset before the full-loop test below

    with tempfile.TemporaryDirectory() as tmp:
        sessions_mod.SESSIONS_DIR = Path(tmp)

        # Full loop: the model writes a todo list, and the NEXT outgoing
        # request's late block must show it -- proving it rides in
        # reminder() rather than being stored as a persisted message.
        write_call = fake_tool_call(
            "call_1",
            "write_todos",
            json.dumps({"todos": [{"content": "look at tools.py", "status": "in_progress"}]}),
        )
        script = [fake_response(tool_calls=[write_call]), fake_response(content="done")]
        client = FakeClient(script)
        mod.make_client = lambda: client
        inputs = iter(["start working on the todo"])

        def fake_get_input():
            try:
                return next(inputs)
            except StopIteration:
                raise EOFError

        mod.ui.get_input = fake_get_input
        with captured_stdout() as out:
            mod.main(argv=[])
        assert "done" in out.getvalue()

        second_request = client.chat.completions.calls[1]["messages"]
        reminder_msg = next(m for m in second_request if "<system-reminder>" in (m["content"] or ""))
        assert "look at tools.py" in reminder_msg["content"]
        assert "[~]" in reminder_msg["content"]  # in_progress marker

        # and it must never appear in a persisted (non-reminder) message
        persisted = [m for m in second_request if "<system-reminder>" not in (m.get("content") or "")]
        assert not any("look at tools.py" in (m.get("content") or "") for m in persisted)


def test_stage_12():
    tools_mod = load_module("stage_12_permissions", "tools.py", mod_name="stage12_tools")
    permissions_mod = sys.modules["permissions"]

    # Simple classification.
    assert permissions_mod.classify_one("ls -la") == "allow"
    assert permissions_mod.classify_one("rm -rf /") == "deny"
    assert permissions_mod.classify_one("rm somefile.txt") == "ask"
    assert permissions_mod.classify_one("some_unknown_tool --flag") == "ask"  # DEFAULT_VERDICT

    # Rule order matters: the specific "git push" rule must win over the
    # general "git" allow rule, since it's checked first.
    assert permissions_mod.classify_one("git push origin main") == "ask"
    assert permissions_mod.classify_one("git status") == "allow"

    # Compound commands: strictest verdict among the pieces wins.
    overall, parts = permissions_mod.classify("ls && rm -rf /")
    assert overall == "deny"
    assert [v for _, v in parts] == ["allow", "deny"]
    overall2, _ = permissions_mod.classify("ls | cat")
    assert overall2 == "allow"

    # bash(): deny short-circuits, the refusal is a normal string result.
    denied = tools_mod.bash("rm -rf /some/path")
    assert denied.startswith("refused:") and "denied" in denied

    # bash(): ask tier, user declines -> refused, nothing runs.
    # tools.py did `from permissions import ask_user`, which copies the
    # name into tools.py's OWN namespace -- patching permissions_mod.ask_user
    # would not be seen by bash(), so we patch tools_mod.ask_user instead.
    tools_mod.ask_user = lambda command: False
    declined = tools_mod.bash("rm harmless_nonexistent_test_file.txt")
    assert declined == "refused: user declined to run this command."

    # bash(): ask tier, user approves -> it actually runs.
    tools_mod.ask_user = lambda command: True
    allowed = tools_mod.bash("rm harmless_nonexistent_test_file.txt")
    assert allowed != "refused: user declined to run this command."

    # bash(): allow tier runs with no prompt at all.
    direct = tools_mod.bash("echo direct")
    assert "direct" in direct


def test_stage_13():
    sandbox_mod = load_module("stage_13_sandbox", "sandbox.py", mod_name="stage13_sandbox")

    status = sandbox_mod.sandbox_status()
    if sandbox_mod.SYSTEM == "Windows":
        assert status.startswith("none")  # no faked enforcement on Windows
    else:
        assert status in ("seatbelt", "bubblewrap") or status.startswith("none")

    assert "hello" in sandbox_mod.run_sandboxed("echo hello")

    # a real timeout must come back as a result string, never an
    # uncaught subprocess.TimeoutExpired
    slow_cmd = f'"{sys.executable}" -c "import time; time.sleep(5)"'
    result = sandbox_mod.run_sandboxed(slow_cmd, timeout=1)
    assert result == "error: command timed out after 1s"

    # the banner now shows sandbox status; confirm main.py actually wires
    # sandbox_status() into ui.banner without needing a live model call
    main_mod = load_module("stage_13_sandbox", "main.py")
    client = FakeClient([fake_response(content="ok")])
    main_mod.make_client = lambda: client

    def immediate_eof():
        raise EOFError

    main_mod.ui.get_input = immediate_eof
    with tempfile.TemporaryDirectory() as tmp:
        sys.modules["sessions"].SESSIONS_DIR = Path(tmp)
        with captured_stdout() as out:
            main_mod.main(argv=[])
    assert "sandbox:" in out.getvalue()


def test_stage_14():
    comp = load_module("stage_14_compaction", "compaction.py", mod_name="stage14_compaction")

    # Mechanism 1: cap_fresh_result.
    comp.FRESH_RESULT_CAP = 50
    short = "x" * 10
    assert comp.cap_fresh_result(short) == short
    long = "y" * 200
    capped = comp.cap_fresh_result(long)
    assert capped != long and "over the 50 cap" in capped
    path = capped.split("full output written to ")[1].split(". read_file")[0]
    assert open(path, encoding="utf-8").read() == long

    # Mechanism 2: shrink_finished_results only touches tool results
    # BEFORE the most recent user message (i.e. a finished turn).
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u1"},
        {"role": "tool", "content": "z" * 1000},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},  # current, in-progress turn starts here
    ]
    assert comp.shrink_finished_results(messages) is True
    assert messages[2]["content"].startswith("(shrunk:")
    assert len(messages[2]["content"]) < 1000
    assert comp.shrink_finished_results(messages) is False  # nothing left to shrink

    # Mechanism 3: drop_old_results, more aggressive, also finished-turn-only.
    messages2 = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u1"},
        {"role": "tool", "content": "z" * 1000},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
    ]
    assert comp.drop_old_results(messages2) is True
    assert messages2[2]["content"] == "(dropped: old tool result, no longer available)"
    assert comp.drop_old_results(messages2) is False

    # Mechanism 4: with nothing cheap to compact (no tool messages at
    # all) and a tiny fake window, compact() must go straight to the
    # no-tools summarizer and collapse the transcript.
    comp.CONTEXT_WINDOW_CHARS = 100
    messages3 = [{"role": "system", "content": "sys"}, {"role": "user", "content": "x" * 500}]
    client = FakeClient([fake_response(content="HANDOFF NOTE TEXT")])
    comp.compact(messages3, client, "some-model")
    assert len(client.chat.completions.calls) == 1
    assert "tools" not in client.chat.completions.calls[0]  # a no-tools call
    assert any("HANDOFF NOTE TEXT" in (m.get("content") or "") for m in messages3)
    assert len(messages3) == 2  # system + one handoff-note message

    # Integration: main.py's run_loop actually calls cap_fresh_result on
    # every tool result before storing it.
    main_mod = load_module("stage_14_compaction", "main.py")
    compaction_mod = sys.modules["compaction"]
    compaction_mod.FRESH_RESULT_CAP = 5
    tool_call = fake_tool_call("call_1", "bash", json.dumps({"command": "echo hello world"}))
    script = [fake_response(tool_calls=[tool_call]), fake_response(content="done")]
    client_a = FakeClient(script)
    main_mod.make_client = lambda: client_a
    inputs_a = iter(["run echo hello world"])

    def get_input_a():
        try:
            return next(inputs_a)
        except StopIteration:
            raise EOFError

    main_mod.ui.get_input = get_input_a
    with tempfile.TemporaryDirectory() as tmp:
        sys.modules["sessions"].SESSIONS_DIR = Path(tmp)
        with captured_stdout():
            main_mod.main(argv=[])
    second_request = client_a.chat.completions.calls[1]["messages"]
    tool_msg = next(m for m in second_request if m["role"] == "tool")
    assert "over the 5 cap" in tool_msg["content"]

    # Integration: main.py's run_loop calls compact() before every
    # request, and mechanism 4 (no tools) precedes the turn's real
    # (with tools) request when the fake window is tiny.
    compaction_mod.CONTEXT_WINDOW_CHARS = 10
    client_b = FakeClient([fake_response(content="HANDOFF"), fake_response(content="final reply")])
    main_mod.make_client = lambda: client_b
    inputs_b = iter(["hello"])

    def get_input_b():
        try:
            return next(inputs_b)
        except StopIteration:
            raise EOFError

    main_mod.ui.get_input = get_input_b
    with tempfile.TemporaryDirectory() as tmp2:
        sys.modules["sessions"].SESSIONS_DIR = Path(tmp2)
        with captured_stdout() as out:
            main_mod.main(argv=[])
    assert "final reply" in out.getvalue()
    calls = client_b.chat.completions.calls
    assert len(calls) == 2
    assert "tools" not in calls[0]  # compact()'s summarizer call
    assert calls[1].get("tools") is not None  # the turn's real call


def test_stage_15():
    subagent_mod = load_module("stage_15_subagents", "subagent.py", mod_name="stage15_subagent")

    # The withheld set must actually be withheld from BOTH collections --
    # from the schema list (the model never learns these exist) and from
    # the function dict (even a hallucinated call resolves to nothing).
    names = {t["function"]["name"] for t in subagent_mod.SUBAGENT_TOOLS}
    assert names == {"bash", "read_file", "read_skill"}
    assert set(subagent_mod.SUBAGENT_FUNCTIONS) == names
    for withheld in ("task", "write_todos", "write_file", "str_replace"):
        assert withheld not in names

    # task() in isolation: it builds its own client and its own empty
    # transcript, resolves one tool call, and returns only the final text.
    sub_tool_call = fake_tool_call("call_s1", "bash", '{"command": "echo from subagent"}')
    sub_script = [
        fake_response(tool_calls=[sub_tool_call]),
        fake_response(content="subagent's final summary"),
    ]
    sub_client = FakeClient(sub_script)
    subagent_mod.make_client = lambda: sub_client
    result = subagent_mod.task("investigate something")
    assert result == "subagent's final summary"
    assert len(sub_client.chat.completions.calls) == 2
    # and the subagent's own request never offered `task` as a tool --
    # proving it truly cannot recurse, not just that it chose not to.
    offered = {t["function"]["name"] for t in sub_client.chat.completions.calls[0]["tools"]}
    assert "task" not in offered

    # Integration: the TOP-LEVEL model calls `task`; only the subagent's
    # final answer becomes the tool result in the PARENT's transcript --
    # the subagent's own tool call/result never appears there.
    main_mod = load_module("stage_15_subagents", "main.py")
    top_subagent_mod = sys.modules["subagent"]
    top_subagent_mod.make_client = lambda: FakeClient(
        [fake_response(content="subagent's final summary")]
    )

    task_call = fake_tool_call("call_1", "task", json.dumps({"prompt": "investigate something"}))
    top_script = [
        fake_response(tool_calls=[task_call]),
        fake_response(content="Here's what I found: subagent's final summary"),
    ]
    top_client = FakeClient(top_script)
    main_mod.make_client = lambda: top_client
    inputs = iter(["please delegate this investigation"])

    def fake_get_input():
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    main_mod.ui.get_input = fake_get_input
    with tempfile.TemporaryDirectory() as tmp:
        sys.modules["sessions"].SESSIONS_DIR = Path(tmp)
        with captured_stdout() as out:
            main_mod.main(argv=[])
    assert "Here's what I found" in out.getvalue()

    second_request = top_client.chat.completions.calls[1]["messages"]
    tool_msg = next(m for m in second_request if m["role"] == "tool")
    assert tool_msg["content"] == "subagent's final summary"
    # the top level's OWN offered tools must include task
    top_level_names = {t["function"]["name"] for t in top_client.chat.completions.calls[0]["tools"]}
    assert "task" in top_level_names


def test_stage_16():
    routing_mod = load_module("stage_16_openrouter_routing", "routing.py", mod_name="stage16_routing")

    # format_route: names show up in order, with a marker on the active one.
    text = routing_mod.format_route(["model_a", "model_b"], active="model_b")
    assert "1. model_a" in text
    last_line = text.strip().splitlines()[-1]
    assert "model_b" in last_line and "<- last used" in last_line

    # set_route replaces wholesale; an empty route is rejected, no mutation.
    before = list(routing_mod.MODELS)
    rejected = routing_mod.set_route([])
    assert rejected.startswith("error:")
    assert routing_mod.MODELS == before
    ok = routing_mod.set_route(["m1", "m2"])
    assert "m1" in ok and routing_mod.MODELS == ["m1", "m2"]

    # call_with_fallback: the first model raises, the second succeeds --
    # both get tried, and usage.include is on every attempt.
    client = FakeClient([RuntimeError("model unavailable"), fake_response(content="ok")])
    response, model_used = routing_mod.call_with_fallback(
        client, ["dead-model", "live-model"], messages=[]
    )
    assert model_used == "live-model"
    assert len(client.chat.completions.calls) == 2
    assert client.chat.completions.calls[0]["extra_body"] == {"usage": {"include": True}}

    # call_with_fallback: every model fails -> the LAST error propagates,
    # rather than being silently swallowed.
    client2 = FakeClient([RuntimeError("first down"), RuntimeError("second down too")])
    try:
        routing_mod.call_with_fallback(client2, ["a", "b"], messages=[])
        raise AssertionError("expected an exception when every model in the route fails")
    except RuntimeError as exc:
        assert "second down too" in str(exc)

    # Integration: a normal turn accumulates SESSION_COST from usage.cost.
    main_mod = load_module("stage_16_openrouter_routing", "main.py")
    client3 = FakeClient([fake_response(content="hi", usage=fake_usage(cost=0.0012345))])
    main_mod.make_client = lambda: client3
    inputs = iter(["hello"])

    def get_input_1():
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    main_mod.ui.get_input = get_input_1
    with tempfile.TemporaryDirectory() as tmp:
        sys.modules["sessions"].SESSIONS_DIR = Path(tmp)
        with captured_stdout() as out:
            main_mod.main(argv=[])
    assert "cost=$0.0012" in out.getvalue()
    assert f"session cost: ${main_mod.SESSION_COST:.6f}" in out.getvalue()
    assert abs(main_mod.SESSION_COST - 0.0012345) < 1e-9

    # /models: shows the route; the slash command never reaches the model.
    client4 = FakeClient([])
    main_mod.make_client = lambda: client4
    inputs2 = iter(["/models"])

    def get_input_2():
        try:
            return next(inputs2)
        except StopIteration:
            raise EOFError

    main_mod.ui.get_input = get_input_2
    with tempfile.TemporaryDirectory() as tmp2:
        sys.modules["sessions"].SESSIONS_DIR = Path(tmp2)
        with captured_stdout() as out2:
            main_mod.main(argv=[])
    assert "route (tried in order" in out2.getvalue()
    assert len(client4.chat.completions.calls) == 0

    # /route: changes the route, and the VERY NEXT real call uses the new
    # first model -- proving main.py reads routing.MODELS live (through
    # the module) rather than a name bound once at import time.
    client5 = FakeClient([fake_response(content="ok", usage=fake_usage(cost=0.0))])
    main_mod.make_client = lambda: client5
    inputs3 = iter(["/route brand-new-model", "second message"])

    def get_input_3():
        try:
            return next(inputs3)
        except StopIteration:
            raise EOFError

    main_mod.ui.get_input = get_input_3
    with tempfile.TemporaryDirectory() as tmp3:
        sys.modules["sessions"].SESSIONS_DIR = Path(tmp3)
        with captured_stdout() as out3:
            main_mod.main(argv=[])
    assert "route set to: brand-new-model" in out3.getvalue()
    assert client5.chat.completions.calls[0]["model"] == "brand-new-model"


STAGES = [
    ("stage_01_minimal_chat", test_stage_01),
    ("stage_02_bash_tool", test_stage_02),
    ("stage_03_tool_registry", test_stage_03),
    ("stage_04_read_file", test_stage_04),
    ("stage_05_agent_loop", test_stage_05),
    ("stage_06_chat_ui", test_stage_06),
    ("stage_07_skills", test_stage_07),
    ("stage_08_file_editing", test_stage_08),
    ("stage_09_late_injection", test_stage_09),
    ("stage_10_sessions", test_stage_10),
    ("stage_11_todos", test_stage_11),
    ("stage_12_permissions", test_stage_12),
    ("stage_13_sandbox", test_stage_13),
    ("stage_14_compaction", test_stage_14),
    ("stage_15_subagents", test_stage_15),
    ("stage_16_openrouter_routing", test_stage_16),
]


def main():
    failures = []
    for name, test_fn in STAGES:
        try:
            test_fn()
        except Exception as exc:  # noqa: BLE001 - report, don't crash the runner
            failures.append((name, exc))
            print(f"{name}: FAILED - {exc}")
        else:
            print(f"{name}: passed")

    print()
    if failures:
        print(f"{len(failures)} of {len(STAGES)} stages failed.")
        sys.exit(1)
    print(f"all {len(STAGES)} stages passed.")


if __name__ == "__main__":
    main()
