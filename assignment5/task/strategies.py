"""The repair-strategy library the ScriptedProposer draws from.

Four kinds of strategy:

  coverage   a handler for one question family. Comes in an "append" variant
             (the natural patch: add it to the end) and a "front" variant
             (insert it first). Same component id, so only one can be present.
  mechanism  a global change: dispatch by priority, link entity mentions to
             canonical values, count distinct entities.
  undo       the inverse of a mechanism, or removal of a handler. These are
             what an improver reaches for when it suspects its last change
             broke something -- the raw material of oscillation.
  shortcut   reward hacks an LLM proposer is known to try. They exist so the
             guard is exercised by real runs, not only by its unit tests.
             Built by the proposer (they need the steering data), listed here.

The starting solver has three hidden problems that interact, by design:
  - shadowing:      a generic "list/which/who ..." handler sits in the list,
                    and first-match dispatch means any handler appended after
                    it never fires for questions it already claims
  - value linking:  B-phrasing questions say "computer engineering" or
                    "cmpe120"; SQLite '=' is case-sensitive, so the literal
                    copied into SQL matches nothing
  - duplicate counting: students retake courses, so COUNT(*) over enrollments
                    overcounts "how many students"
Each one makes an otherwise-correct coverage fix look useless, which is the
condition under which first-order RSI thrashes.
"""
from __future__ import annotations

from dataclasses import dataclass

from task.solver_state import Component, SolverState

# --------------------------------------------------------------------------
# The deliberately weak starting solver
# --------------------------------------------------------------------------
BASE_COMPONENTS = (
    Component("s1_admitted", r'''
m = re.search(r"students?\b.*\badmitted in (\d{4})", q, re.I)
if m:
    return f"SELECT name FROM students WHERE admit_year = {m.group(1)}"
'''),
    Component("s2_subject_courses", r'''
m = re.search(r"titles of all ([A-Z]{2,5}) courses|subject code ([A-Z]{2,5})", q)
if m:
    return f"SELECT title FROM courses WHERE subject = {sql_str(m.group(1) or m.group(2))}"
'''),
    Component("s3_hired", r'''
m = re.search(r"instructors? (?:were )?hired in (\d{4})", q, re.I)
if m:
    return f"SELECT name FROM instructors WHERE hire_year = {m.group(1)}"
'''),
    Component("s5_course_title", r'''
m = re.search(r"title of (?:course )?([A-Z]{2,5} \d{3})", q)
if m:
    return f"SELECT title FROM courses WHERE code = {sql_str(m.group(1))}"
'''),
    Component("s6_student_by_id", r'''
m = re.search(r"student (?:with|has) ID (\d+)", q, re.I)
if m:
    return f"SELECT name FROM students WHERE student_id = {m.group(1)}"
'''),
    Component("generic_list", r'''
m = re.match(r"\s*(?:list|which|show|who|give|name)\b.*?"
             r"\b(student|course|instructor|section|department)s?\b", q, re.I)
if m:
    table = m.group(1).lower()
    column = {"student": "name", "course": "title", "instructor": "name",
              "section": "section_id", "department": "name"}[table]
    return f"SELECT {column} FROM {table}s"
''', priority=0),
)


def initial_state() -> SolverState:
    return SolverState(components=BASE_COMPONENTS)


BASE_CIDS = frozenset(c.cid for c in BASE_COMPONENTS)

# --------------------------------------------------------------------------
# Coverage handlers, one per family the starting solver cannot answer
# --------------------------------------------------------------------------
_DEPT_JOIN = "JOIN departments d ON {a}.dept_id = d.dept_id"
_GRADES = ("JOIN enrollments e ON e.student_id = s.student_id "
           "JOIN grades g ON g.enrollment_id = e.enrollment_id")
_COURSE = ("JOIN sections s ON e.section_id = s.section_id "
           "JOIN courses c ON s.course_id = c.course_id")

COVERAGE = {
    "S4": ("s4_capacity", r'''
m = re.search(r"(?:capacity greater than|seat more than) (\d+)", q, re.I)
if m:
    return f"SELECT section_id FROM sections WHERE capacity > {m.group(1)}"
'''),
    "J1": ("j1_courses_by_dept", r'''
m = re.search(r"^(?:list|which)\b.*?courses (?:offered by the (.+?) department"
              r"|does the (.+?) department offer)", q, re.I)
if m:
    return ("SELECT c.title FROM courses c ''' + _DEPT_JOIN.format(a="c") + r''' "
            f"WHERE d.name = {sql_str(m.group(1) or m.group(2))}")
'''),
    "J2": ("j2_students_in_dept", r'''
m = re.search(r"^(?:which|list)\b.*?students (?:are majoring in (.+?)\?"
              r"|in the (.+?) department\.)$", q, re.I)
if m:
    return ("SELECT s.name FROM students s ''' + _DEPT_JOIN.format(a="s") + r''' "
            f"WHERE d.name = {sql_str(m.group(1) or m.group(2))}")
'''),
    "J3": ("j3_instructors_course_term", r'''
m = re.search(r"^(?:who|which instructors) taught " + CODE + r" (?:in|during) " + TERM,
              q, re.I)
if m:
    return ("SELECT DISTINCT i.name FROM instructors i "
            "JOIN sections s ON s.instructor_id = i.instructor_id "
            "JOIN courses c ON s.course_id = c.course_id "
            "JOIN terms t ON s.term_id = t.term_id "
            f"WHERE c.code = {sql_str(m.group(1))} AND t.name = {sql_str(m.group(2))}")
'''),
    "J4": ("j4_students_course_term", r'''
m = re.search(r"^(?:list the students enrolled in|who took) " + CODE
              + r" (?:during|in) " + TERM, q, re.I)
if m:
    return ("SELECT st.name FROM students st "
            "JOIN enrollments e ON e.student_id = st.student_id "
            "''' + _COURSE + r''' JOIN terms t ON s.term_id = t.term_id "
            f"WHERE c.code = {sql_str(m.group(1))} AND t.name = {sql_str(m.group(2))}")
'''),
    "A1": ("a1_count_students_dept", r'''
m = re.search(r"^(?:how many students are in the (.+?) department"
              r"|what is the number of students majoring in (.+?))\?$", q, re.I)
if m:
    return ("SELECT COUNT(*) FROM students s ''' + _DEPT_JOIN.format(a="s") + r''' "
            f"WHERE d.name = {sql_str(m.group(1) or m.group(2))}")
'''),
    "A2": ("a2_students_in_term", r'''
m = re.search(r"^how many (?:different )?students (?:enrolled|took classes) in " + TERM,
              q, re.I)
if m:
    return (f"SELECT {count_expr('e.student_id')} FROM enrollments e "
            "JOIN sections s ON e.section_id = s.section_id "
            "JOIN terms t ON s.term_id = t.term_id "
            f"WHERE t.name = {sql_str(m.group(1))}")
'''),
    "A3": ("a3_avg_grade_course", r'''
m = re.search(r"^what is the (?:average grade point in|mean grade for) " + CODE, q, re.I)
if m:
    return ("SELECT AVG(g.points) FROM grades g "
            "JOIN enrollments e ON g.enrollment_id = e.enrollment_id "
            "''' + _COURSE + r''' "
            f"WHERE c.code = {sql_str(m.group(1))}")
'''),
    "A4": ("a4_students_took_course", r'''
m = re.search(r"^how many (?:distinct )?students (?:have taken|enrolled in) " + CODE,
              q, re.I)
if m:
    return (f"SELECT {count_expr('e.student_id')} FROM enrollments e "
            "''' + _COURSE + r''' "
            f"WHERE c.code = {sql_str(m.group(1))}")
'''),
    "G1": ("g1_admitted_per_year", r'''
m = re.search(r"^(?:in the (.+?) department, how many students were admitted each year"
              r"|how many (.+?) students were admitted per year)\?$", q, re.I)
if m:
    return ("SELECT s.admit_year, COUNT(*) FROM students s ''' + _DEPT_JOIN.format(a="s")
            + r''' "
            f"WHERE d.name = {sql_str(m.group(1) or m.group(2))} GROUP BY s.admit_year")
'''),
    "G2": ("g2_sections_per_course", r'''
m = re.search(r"^(?:for each ([A-Za-z]{2,5}) course that has been offered, how many "
              r"sections were there|how many sections has each ([A-Za-z]{2,5}) course "
              r"had)\?$", q, re.I)
if m:
    return ("SELECT c.code, COUNT(*) FROM courses c "
            "JOIN sections s ON s.course_id = c.course_id "
            f"WHERE c.subject = {sql_str(m.group(1) or m.group(2))} GROUP BY c.code")
'''),
    "O1": ("o1_courses_by_code", r'''
m = re.search(r"^(?:list the courses in the (.+?) department ordered by course code"
              r"|give the (.+?) department's course titles sorted by code)\.$", q, re.I)
if m:
    return ("SELECT c.title FROM courses c ''' + _DEPT_JOIN.format(a="c") + r''' "
            f"WHERE d.name = {sql_str(m.group(1) or m.group(2))} ORDER BY c.code")
'''),
    "O2": ("o2_top_students", r'''
m = re.search(r"^(?:who are the top (\d+) students by average grade in the (.+?) "
              r"department\?|name the (\d+) best students in (.+?) by average grade, "
              r"highest first\.)$", q, re.I)
if m:
    k, dept = (m.group(1) or m.group(3)), (m.group(2) or m.group(4))
    return ("SELECT s.name FROM students s ''' + _DEPT_JOIN.format(a="s") + " " + _GRADES
            + r''' "
            f"WHERE d.name = {sql_str(dept)} GROUP BY s.student_id "
            f"ORDER BY AVG(g.points) DESC LIMIT {k}")
'''),
    "Q1": ("q1_never_offered", r'''
m = re.search(r"^(?:which ([A-Za-z]{2,5}) courses have never been offered\?"
              r"|list the ([A-Za-z]{2,5}) courses that have no sections\.)$", q, re.I)
if m:
    return (f"SELECT title FROM courses WHERE subject = {sql_str(m.group(1) or m.group(2))} "
            "AND course_id NOT IN (SELECT course_id FROM sections)")
'''),
    "Q2": ("q2_above_average", r'''
m = re.search(r"^(?:which students in the (.+?) department have an average grade above "
              r"the university average|who in (.+?) has an average grade higher than "
              r"the overall average)\?$", q, re.I)
if m:
    return ("SELECT s.name FROM students s ''' + _DEPT_JOIN.format(a="s") + " " + _GRADES
            + r''' "
            f"WHERE d.name = {sql_str(m.group(1) or m.group(2))} GROUP BY s.student_id "
            "HAVING AVG(g.points) > (SELECT AVG(points) FROM grades)")
'''),
}

# Hand-written DISTINCT variants: a first-order route around duplicate counting.
DISTINCT_VARIANTS = {
    "A2": COVERAGE["A2"][1].replace("{count_expr('e.student_id')}",
                                    "COUNT(DISTINCT e.student_id)"),
    "A4": COVERAGE["A4"][1].replace("{count_expr('e.student_id')}",
                                    "COUNT(DISTINCT e.student_id)"),
}


@dataclass(frozen=True)
class Strategy:
    sid: str
    kind: str               # add_handler | set_flag | remove_handler
    mechanism: str          # coverage | shadowing | value_linking | duplicate_counting | undo
    description: str
    family: str | None = None
    component: Component | None = None
    position: str = "append"
    flag: str | None = None
    value: object = None
    weight: float = 1.0

    @property
    def edit_key(self) -> str:
        if self.kind == "add_handler":
            return f"add:{self.component.cid}"
        if self.kind == "set_flag":
            return f"flag:{self.flag}={self.value}"
        return f"remove:{self.sid.split(':', 1)[1]}"


def _coverage_strategies() -> list[Strategy]:
    out = []
    for fam, (cid, body) in COVERAGE.items():
        comp = Component(cid, body, origin=f"fix_{fam}")
        out.append(Strategy(f"fix_{fam}", "add_handler", "coverage",
                            f"add a handler for {fam} at the end of the dispatch list",
                            family=fam, component=comp, position="append", weight=3.0))
        out.append(Strategy(f"fix_{fam}_front", "add_handler", "coverage",
                            f"add a handler for {fam} at the front of the dispatch list",
                            family=fam, component=Component(cid, body, origin=f"fix_{fam}_front"),
                            position="prepend", weight=1.0))
    for fam, body in DISTINCT_VARIANTS.items():
        cid = COVERAGE[fam][0]
        out.append(Strategy(f"fix_{fam}_distinct", "add_handler", "coverage",
                            f"add a {fam} handler that hard-codes COUNT(DISTINCT ...)",
                            family=fam, component=Component(cid, body,
                                                            origin=f"fix_{fam}_distinct"),
                            position="append", weight=1.0))
    return out


MECHANISMS = [
    Strategy("dispatch_priority", "set_flag", "shadowing",
             "dispatch handlers by priority so generic handlers run last",
             flag="DISPATCH", value="priority"),
    Strategy("link_entities", "set_flag", "value_linking",
             "rewrite entity mentions to canonical stored values before matching",
             flag="LINK_ENTITIES", value=True),
    Strategy("count_distinct", "set_flag", "duplicate_counting",
             "count distinct entities instead of joined rows",
             flag="COUNT_DISTINCT", value=True),
]

UNDO_FLAGS = [
    Strategy("dispatch_list", "set_flag", "undo", "go back to first-match list dispatch",
             flag="DISPATCH", value="list"),
    Strategy("unlink_entities", "set_flag", "undo", "stop rewriting entity mentions",
             flag="LINK_ENTITIES", value=False),
    Strategy("count_rows", "set_flag", "undo", "count joined rows again",
             flag="COUNT_DISTINCT", value=False),
]

COVERAGE_STRATEGIES = _coverage_strategies()
BY_ID = {s.sid: s for s in COVERAGE_STRATEGIES + MECHANISMS + UNDO_FLAGS}
MECHANISM_FOR_CAUSE = {s.mechanism: s for s in MECHANISMS}


def removal(cid: str) -> Strategy:
    return Strategy(f"remove:{cid}", "remove_handler", "undo",
                    f"remove the {cid} handler", weight=1.0)


def inverse_key(edit_key: str) -> str | None:
    """The edit that would undo `edit_key`, for oscillation detection."""
    if edit_key.startswith("add:"):
        return "remove:" + edit_key[4:]
    if edit_key.startswith("remove:"):
        return "add:" + edit_key[7:]
    if edit_key.startswith("flag:"):
        name, value = edit_key[5:].split("=", 1)
        flip = {"True": "False", "False": "True", "priority": "list", "list": "priority"}
        return f"flag:{name}={flip.get(value, value)}"
    return None


def applicable(strategy: Strategy, state: SolverState) -> bool:
    if strategy.kind == "add_handler":
        return not state.has(strategy.component.cid)
    if strategy.kind == "set_flag":
        return state.flag(strategy.flag) != strategy.value
    if strategy.kind == "remove_handler":
        return state.has(strategy.sid.split(":", 1)[1])
    return False
