"""The 120-question benchmark: 20 families x 6 instances.

Each family is one kind of question (a join, an aggregate, a subquery...)
with two phrasings:
  A -- canonical surface forms ("Computer Engineering", "CMPE 120", "Fall 2024")
  B -- a different sentence AND, for most families, a user-style surface
       form ("computer engineering", "cmpe120", "fall 2024")
SQLite's '=' is case-sensitive, so a solver that copies the B literal
straight into SQL gets an empty result. That is the value-linking problem
every real NL2SQL system has, and it is one of the root causes the methods
in this assignment have to find.

Instance i of a family gets phrasing i % 2 and split i // 2, so every split
holds exactly one A and one B instance of every family: 20 families x 2 =
40 questions per split, with no family missing from any split.

Run `python -m task.questions` to regenerate task/data/*.json. The files are
committed; tests/test_task.py checks they still match a fresh build.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from task import db

SPLITS = ("steering", "validation", "heldout")
DATA_DIR = Path(__file__).parent / "data"
INSTANCES_PER_FAMILY = 6

CATEGORY = {
    "S": "simple select", "J": "join", "A": "aggregate", "G": "group by",
    "O": "ordering", "Q": "subquery",
}


@dataclass(frozen=True)
class Family:
    fid: str
    pool: str                 # which parameter pool to draw from
    phrasings: tuple[str, str]
    gold: str
    ordered: bool = False
    check: str = ""           # extra validity rule for an instance


def _q(v: str) -> str:
    return v.replace("'", "''")


DEPT_JOIN = "JOIN departments d ON {a}.dept_id = d.dept_id"
ENROLL_CHAIN = ("JOIN enrollments e ON e.student_id = s.student_id "
                "JOIN grades g ON g.enrollment_id = e.enrollment_id")
COURSE_CHAIN = ("JOIN sections s ON e.section_id = s.section_id "
                "JOIN courses c ON s.course_id = c.course_id")

FAMILIES = [
    # ---- simple selects: the weak starting solver handles S1-S3, S5, S6 ----
    Family("S1", "admit_year",
           ("List the names of students admitted in {year}.",
            "Which students were admitted in {year}?"),
           "SELECT name FROM students WHERE admit_year = {year}"),
    Family("S2", "subject",
           ("List the titles of all {subject} courses.",
            "Which courses have the subject code {subject}?"),
           "SELECT title FROM courses WHERE subject = '{subject}'"),
    Family("S3", "hire_year",
           ("Which instructors were hired in {year}?",
            "List the instructors hired in {year}."),
           "SELECT name FROM instructors WHERE hire_year = {year}"),
    Family("S4", "capacity",
           ("Which sections have a capacity greater than {n}?",
            "List the sections that can seat more than {n} students."),
           "SELECT section_id FROM sections WHERE capacity > {n}"),
    Family("S5", "course_code",
           ("What is the title of course {code}?",
            "Give the title of {code}."),
           "SELECT title FROM courses WHERE code = '{code}'"),
    Family("S6", "student_id",
           ("What is the name of the student with ID {sid}?",
            "Which student has ID {sid}?"),
           "SELECT name FROM students WHERE student_id = {sid}"),
    # ---- joins ----
    Family("J1", "dept",
           ("List the titles of courses offered by the {dept} department.",
            "Which courses does the {dept_v} department offer?"),
           "SELECT c.title FROM courses c " + DEPT_JOIN.format(a="c")
           + " WHERE d.name = '{dept}'"),
    Family("J2", "dept",
           ("Which students are majoring in {dept}?",
            "List the students in the {dept_v} department."),
           "SELECT s.name FROM students s " + DEPT_JOIN.format(a="s")
           + " WHERE d.name = '{dept}'"),
    Family("J3", "course_term",
           ("Who taught {code} in {term}?",
            "Which instructors taught {code_v} during {term_v}?"),
           "SELECT DISTINCT i.name FROM instructors i "
           "JOIN sections s ON s.instructor_id = i.instructor_id "
           "JOIN courses c ON s.course_id = c.course_id "
           "JOIN terms t ON s.term_id = t.term_id "
           "WHERE c.code = '{code}' AND t.name = '{term}'"),
    Family("J4", "course_term",
           ("List the students enrolled in {code} during {term}.",
            "Who took {code_v} in {term_v}?"),
           "SELECT st.name FROM students st "
           "JOIN enrollments e ON e.student_id = st.student_id "
           + COURSE_CHAIN + " JOIN terms t ON s.term_id = t.term_id "
           "WHERE c.code = '{code}' AND t.name = '{term}'"),
    # ---- aggregates ----
    Family("A1", "dept",
           ("How many students are in the {dept} department?",
            "What is the number of students majoring in {dept_v}?"),
           "SELECT COUNT(*) FROM students s " + DEPT_JOIN.format(a="s")
           + " WHERE d.name = '{dept}'"),
    Family("A2", "term",
           ("How many different students enrolled in {term}?",
            "How many students took classes in {term_v}?"),
           "SELECT COUNT(DISTINCT e.student_id) FROM enrollments e "
           "JOIN sections s ON e.section_id = s.section_id "
           "JOIN terms t ON s.term_id = t.term_id WHERE t.name = '{term}'"),
    Family("A3", "graded_course",
           ("What is the average grade point in {code}?",
            "What is the mean grade for {code_v}?"),
           "SELECT ROUND(AVG(g.points), 2) FROM grades g "
           "JOIN enrollments e ON g.enrollment_id = e.enrollment_id "
           + COURSE_CHAIN + " WHERE c.code = '{code}'"),
    Family("A4", "retaken_course",
           ("How many students have taken {code}?",
            "How many distinct students enrolled in {code_v}?"),
           "SELECT COUNT(DISTINCT e.student_id) FROM enrollments e "
           + COURSE_CHAIN + " WHERE c.code = '{code}'"),
    # ---- group by ----
    Family("G1", "dept",
           ("In the {dept} department, how many students were admitted each year?",
            "How many {dept_v} students were admitted per year?"),
           "SELECT s.admit_year, COUNT(*) FROM students s " + DEPT_JOIN.format(a="s")
           + " WHERE d.name = '{dept}' GROUP BY s.admit_year"),
    Family("G2", "subject",
           ("For each {subject} course that has been offered, how many sections were there?",
            "How many sections has each {subject_v} course had?"),
           "SELECT c.code, COUNT(*) FROM courses c "
           "JOIN sections s ON s.course_id = c.course_id "
           "WHERE c.subject = '{subject}' GROUP BY c.code"),
    # ---- ordering (compared as ordered lists) ----
    Family("O1", "dept",
           ("List the courses in the {dept} department ordered by course code.",
            "Give the {dept_v} department's course titles sorted by code."),
           "SELECT c.title FROM courses c " + DEPT_JOIN.format(a="c")
           + " WHERE d.name = '{dept}' ORDER BY c.code", ordered=True),
    Family("O2", "dept_k",
           ("Who are the top {k} students by average grade in the {dept} department?",
            "Name the {k} best students in {dept_v} by average grade, highest first."),
           "SELECT s.name FROM students s " + DEPT_JOIN.format(a="s") + " "
           + ENROLL_CHAIN + " WHERE d.name = '{dept}' GROUP BY s.student_id "
           "ORDER BY AVG(g.points) DESC LIMIT {k}", ordered=True, check="no_ties"),
    # ---- subqueries ----
    Family("Q1", "subject",
           ("Which {subject} courses have never been offered?",
            "List the {subject_v} courses that have no sections."),
           "SELECT title FROM courses WHERE subject = '{subject}' "
           "AND course_id NOT IN (SELECT course_id FROM sections)"),
    Family("Q2", "dept",
           ("Which students in the {dept} department have an average grade above "
            "the university average?",
            "Who in {dept_v} has an average grade higher than the overall average?"),
           "SELECT s.name FROM students s " + DEPT_JOIN.format(a="s") + " "
           + ENROLL_CHAIN + " WHERE d.name = '{dept}' GROUP BY s.student_id "
           "HAVING AVG(g.points) > (SELECT AVG(points) FROM grades)"),
]


def _code_variant(code: str, rng: np.random.Generator) -> str:
    subject, num = code.split()
    forms = [f"{subject.lower()}{num}", f"{subject}-{num}", f"{subject.lower()} {num}"]
    return forms[int(rng.integers(len(forms)))]


def _pools(conn) -> dict[str, list[dict]]:
    one = lambda sql: [r[0] for r in conn.execute(sql).fetchall()]
    dept = [{"dept": d} for d in one("SELECT name FROM departments")]
    return {
        "admit_year": [{"year": y} for y in one("SELECT DISTINCT admit_year FROM students")],
        "hire_year": [{"year": y} for y in one("SELECT DISTINCT hire_year FROM instructors")],
        "subject": [{"subject": s} for s in one("SELECT DISTINCT subject FROM courses")],
        "capacity": [{"n": n} for n in (25, 35, 40, 45, 50, 60, 80)],
        "course_code": [{"code": c} for c in one("SELECT code FROM courses")],
        "student_id": [{"sid": i} for i in one("SELECT student_id FROM students")],
        "dept": dept,
        "dept_k": [{**d, "k": k} for d in dept for k in (3, 5)],
        "term": [{"term": t} for t in one("SELECT name FROM terms")],
        "course_term": [{"code": c, "term": t} for c, t in conn.execute(
            "SELECT DISTINCT c.code, t.name FROM sections s "
            "JOIN courses c ON s.course_id = c.course_id "
            "JOIN terms t ON s.term_id = t.term_id").fetchall()],
        "graded_course": [{"code": c} for c in one(
            "SELECT DISTINCT c.code FROM grades g "
            "JOIN enrollments e ON g.enrollment_id = e.enrollment_id "
            "JOIN sections s ON e.section_id = s.section_id "
            "JOIN courses c ON s.course_id = c.course_id")],
        # Courses some student took more than once: COUNT(*) != COUNT(DISTINCT).
        "retaken_course": [{"code": c} for c in one(
            "SELECT c.code FROM enrollments e "
            "JOIN sections s ON e.section_id = s.section_id "
            "JOIN courses c ON s.course_id = c.course_id GROUP BY c.code "
            "HAVING COUNT(*) > COUNT(DISTINCT e.student_id)")],
    }


def normalize_rows(rows, ordered: bool):
    """Canonical form for comparison: floats to 2dp; a list if order matters,
    otherwise a sorted list of distinct rows (set semantics, JSON-friendly)."""
    norm = [tuple(round(v, 2) if isinstance(v, float) else v for v in r) for r in rows]
    if ordered:
        return [list(r) for r in norm]
    return [list(r) for r in sorted(set(norm), key=repr)]


def _valid(fam: Family, params: dict, rows, conn) -> bool:
    if not rows or rows == [(None,)]:
        return False                       # an empty gold set is matched by broken SQL
    if fam.check == "no_ties":
        sql = fam.gold.format(**params).replace(
            "SELECT s.name", "SELECT AVG(g.points)").replace(
            f"LIMIT {params['k']}", f"LIMIT {params['k'] + 1}")
        avgs = [round(r[0], 9) for r in conn.execute(sql).fetchall()]
        if len(set(avgs)) != len(avgs):
            return False                   # a tie would make the gold order arbitrary
    return True


def build(seed: int = db.SEED) -> dict[str, list[dict]]:
    conn = db.connect(seed)
    rng = np.random.default_rng(seed)
    pools = _pools(conn)
    splits: dict[str, list[dict]] = {s: [] for s in SPLITS}
    for fam in FAMILIES:
        pool = pools[fam.pool]
        order = rng.permutation(len(pool))
        made = 0
        for j in order:
            if made == INSTANCES_PER_FAMILY:
                break
            params = dict(pool[int(j)])
            if "dept" in params:
                params["dept_v"] = params["dept"].lower()
            if "code" in params:
                params["code_v"] = _code_variant(params["code"], rng)
            if "term" in params:
                params["term_v"] = params["term"].lower()
            if "subject" in params:
                params["subject_v"] = params["subject"].lower()
            gold_sql = fam.gold.format(**{k: _q(str(v)) for k, v in params.items()})
            rows = conn.execute(gold_sql).fetchall()
            if not _valid(fam, params, rows, conn):
                continue
            phrasing = made % 2
            splits[SPLITS[made // 2]].append({
                "qid": f"{fam.fid}-{made}",
                "family": fam.fid,
                "category": CATEGORY[fam.fid[0]],
                "phrasing": "AB"[phrasing],
                "question": fam.phrasings[phrasing].format(**params),
                "gold_sql": gold_sql,
                "ordered": fam.ordered,
                "gold_result": normalize_rows(rows, fam.ordered),
            })
            made += 1
        if made < INSTANCES_PER_FAMILY:
            raise RuntimeError(f"family {fam.fid}: only {made} valid instances")
    return splits


def write(splits: dict[str, list[dict]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, items in splits.items():
        (DATA_DIR / f"{name}.json").write_text(json.dumps(items, indent=1), encoding="utf-8")


if __name__ == "__main__":
    built = build()
    write(built)
    for name, items in built.items():
        print(f"{name:10s} {len(items)} questions")
