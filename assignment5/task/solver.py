"""solver.py -- natural language to SQL for the university database.

GENERATED from a SolverState by task/solver_state.py. Each RSI method edits
the state, never this text directly. Components run in dispatch order; the
first one that returns SQL wins.
"""
import re

from task.db import schema_info

SCHEMA = schema_info()
SUBJECTS = set(SCHEMA["subjects"])
CODE = r"([A-Za-z]{2,5}[ -]?\d{3})\b"
TERM = r"((?:[Ff]all|[Ss]pring) \d{4})"

FLAGS = {'COUNT_DISTINCT': False, 'DISPATCH': 'list', 'LINK_ENTITIES': False}


def sql_str(value):
    return "'" + str(value).replace("'", "''") + "'"


def count_expr(column):
    return f"COUNT(DISTINCT {column})" if FLAGS["COUNT_DISTINCT"] else "COUNT(*)"


def link_entities(q):
    """Rewrite user-style entity mentions to the stored canonical values."""
    for name in SCHEMA["departments"]:
        q = re.sub(re.escape(name), name, q, flags=re.I)
    for term in SCHEMA["terms"]:
        q = re.sub(re.escape(term), term, q, flags=re.I)

    def _code(m):
        subject = m.group(1).upper()
        return f"{subject} {m.group(2)}" if subject in SUBJECTS else m.group(0)

    q = re.sub(r"\b([A-Za-z]{2,5})[ -]?(\d{3})\b", _code, q)
    return re.sub(r"\b([a-z]{2,5})\b",
                  lambda m: m.group(1).upper() if m.group(1).upper() in SUBJECTS
                  else m.group(0), q)


HANDLERS = []


def handler(name, priority=50):
    def register(fn):
        HANDLERS.append((name, priority, fn))
        return fn
    return register


@handler("s1_admitted", 50)
def h_s1_admitted(q):
    m = re.search(r"students?\b.*\badmitted in (\d{4})", q, re.I)
    if m:
        return f"SELECT name FROM students WHERE admit_year = {m.group(1)}"

@handler("s2_subject_courses", 50)
def h_s2_subject_courses(q):
    m = re.search(r"titles of all ([A-Z]{2,5}) courses|subject code ([A-Z]{2,5})", q)
    if m:
        return f"SELECT title FROM courses WHERE subject = {sql_str(m.group(1) or m.group(2))}"

@handler("s3_hired", 50)
def h_s3_hired(q):
    m = re.search(r"instructors? (?:were )?hired in (\d{4})", q, re.I)
    if m:
        return f"SELECT name FROM instructors WHERE hire_year = {m.group(1)}"

@handler("s5_course_title", 50)
def h_s5_course_title(q):
    m = re.search(r"title of (?:course )?([A-Z]{2,5} \d{3})", q)
    if m:
        return f"SELECT title FROM courses WHERE code = {sql_str(m.group(1))}"

@handler("s6_student_by_id", 50)
def h_s6_student_by_id(q):
    m = re.search(r"student (?:with|has) ID (\d+)", q, re.I)
    if m:
        return f"SELECT name FROM students WHERE student_id = {m.group(1)}"

@handler("generic_list", 0)
def h_generic_list(q):
    m = re.match(r"\s*(?:list|which|show|who|give|name)\b.*?"
                 r"\b(student|course|instructor|section|department)s?\b", q, re.I)
    if m:
        table = m.group(1).lower()
        column = {"student": "name", "course": "title", "instructor": "name",
                  "section": "section_id", "department": "name"}[table]
        return f"SELECT {column} FROM {table}s"


def dispatch_order():
    if FLAGS["DISPATCH"] == "priority":
        return sorted(HANDLERS, key=lambda h: -h[1])     # stable: ties keep list order
    return HANDLERS


def trace(question):
    q = link_entities(question) if FLAGS["LINK_ENTITIES"] else question
    for name, _priority, fn in dispatch_order():
        sql = fn(q)
        if sql:
            return name, sql
    return "fallback", "SELECT NULL WHERE 0"


def solve(question):
    return trace(question)[1]


if __name__ == "__main__":
    import sys
    print(solve(" ".join(sys.argv[1:])))
