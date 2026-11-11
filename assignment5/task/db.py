"""The seeded university course-enrollment database.

Eight tables, built in memory from numpy's default_rng(42) so every process
sees byte-identical data and nothing is downloaded. Building takes a few
milliseconds, so there is no cached .db file to drift out of sync.

The data is shaped on purpose, because the question set depends on it:
  - some courses are never offered (gives "never offered" subqueries a
    non-empty answer for every subject)
  - students retake courses across terms (so COUNT(*) over enrollments and
    COUNT(DISTINCT student_id) disagree -- a real NL2SQL trap)
  - the newest term has no grades yet (in-progress term)
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache

import numpy as np

SEED = 42

DEPARTMENTS = [
    # (name, code, building)
    ("Computer Engineering", "CMPE", "Engineering Hall"),
    ("Mathematics", "MATH", "Science Tower"),
    ("Physics", "PHYS", "Science Tower"),
    ("Chemistry", "CHEM", "Duncan Hall"),
    ("Biology", "BIOL", "Duncan Hall"),
    ("History", "HIST", "Clark Hall"),
    ("Economics", "ECON", "Boccardo Hall"),
    ("English", "ENGL", "Clark Hall"),
]

COURSE_TITLES = {
    "CMPE": ["Programming Fundamentals", "Data Structures", "Computer Architecture",
             "Operating Systems", "Computer Networks", "Machine Learning",
             "Compiler Design", "Distributed Systems"],
    "MATH": ["Calculus I", "Calculus II", "Linear Algebra", "Discrete Mathematics",
             "Probability", "Real Analysis", "Number Theory", "Numerical Methods"],
    "PHYS": ["Mechanics", "Electromagnetism", "Thermodynamics", "Quantum Physics",
             "Optics", "Astrophysics", "Solid State Physics", "Modern Physics"],
    "CHEM": ["General Chemistry", "Organic Chemistry", "Physical Chemistry",
             "Analytical Chemistry", "Biochemistry", "Inorganic Chemistry",
             "Polymer Science", "Chemical Kinetics"],
    "BIOL": ["Cell Biology", "Genetics", "Ecology", "Microbiology", "Evolution",
             "Neuroscience", "Marine Biology", "Immunology"],
    "HIST": ["World History", "American History", "Medieval Europe", "Modern Asia",
             "History of Science", "Ancient Rome", "Cold War", "Latin America"],
    "ECON": ["Microeconomics", "Macroeconomics", "Econometrics", "Game Theory",
             "Public Finance", "Labor Economics", "Development Economics",
             "International Trade"],
    "ENGL": ["Composition", "Shakespeare", "Modern Poetry", "The Novel",
             "Creative Writing", "Rhetoric", "American Literature", "Literary Theory"],
}

FIRST_NAMES = ["Ava", "Ben", "Chloe", "Dev", "Elena", "Farid", "Grace", "Hiro", "Isla",
               "Jonah", "Kira", "Leo", "Maya", "Nikhil", "Olivia", "Priya", "Quinn",
               "Rafael", "Sofia", "Theo", "Uma", "Victor", "Wen", "Xavier", "Yara",
               "Zane", "Amara", "Bruno", "Carmen", "Dmitri"]
LAST_NAMES = ["Abbott", "Banerjee", "Castillo", "Dubois", "Eriksen", "Fujita", "Garcia",
              "Haddad", "Iyer", "Jensen", "Kowalski", "Lindqvist", "Moreau", "Nakamura",
              "Okafor", "Petrov", "Quintero", "Rossi", "Sato", "Tanaka", "Umarov",
              "Varga", "Walsh", "Xu", "Yilmaz", "Zhang", "Alvarez", "Brennan", "Chen",
              "Delgado"]

RANKS = ["Lecturer", "Assistant Professor", "Associate Professor", "Professor"]
TERMS = [("Fall 2023", 2023, "Fall"), ("Spring 2024", 2024, "Spring"),
         ("Fall 2024", 2024, "Fall"), ("Spring 2025", 2025, "Spring"),
         ("Fall 2025", 2025, "Fall"), ("Spring 2026", 2026, "Spring")]
IN_PROGRESS_TERM = "Spring 2026"
GRADE_SCALE = [("A", 4.0), ("A-", 3.7), ("B+", 3.3), ("B", 3.0), ("B-", 2.7),
               ("C+", 2.3), ("C", 2.0), ("C-", 1.7), ("D", 1.0), ("F", 0.0)]

N_INSTRUCTORS = 40
N_STUDENTS = 300

SCHEMA_SQL = """
CREATE TABLE departments (dept_id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                          code TEXT NOT NULL, building TEXT NOT NULL);
CREATE TABLE instructors (instructor_id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                          dept_id INTEGER NOT NULL REFERENCES departments(dept_id),
                          rank TEXT NOT NULL, hire_year INTEGER NOT NULL);
CREATE TABLE students (student_id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                       dept_id INTEGER NOT NULL REFERENCES departments(dept_id),
                       admit_year INTEGER NOT NULL);
CREATE TABLE courses (course_id INTEGER PRIMARY KEY,
                      dept_id INTEGER NOT NULL REFERENCES departments(dept_id),
                      subject TEXT NOT NULL, code TEXT NOT NULL, title TEXT NOT NULL,
                      credits INTEGER NOT NULL, level INTEGER NOT NULL);
CREATE TABLE terms (term_id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                    year INTEGER NOT NULL, season TEXT NOT NULL);
CREATE TABLE sections (section_id INTEGER PRIMARY KEY,
                       course_id INTEGER NOT NULL REFERENCES courses(course_id),
                       term_id INTEGER NOT NULL REFERENCES terms(term_id),
                       instructor_id INTEGER NOT NULL REFERENCES instructors(instructor_id),
                       capacity INTEGER NOT NULL, room TEXT NOT NULL);
CREATE TABLE enrollments (enrollment_id INTEGER PRIMARY KEY,
                          student_id INTEGER NOT NULL REFERENCES students(student_id),
                          section_id INTEGER NOT NULL REFERENCES sections(section_id));
CREATE TABLE grades (enrollment_id INTEGER PRIMARY KEY
                         REFERENCES enrollments(enrollment_id),
                     letter TEXT NOT NULL, points REAL NOT NULL);
"""

TABLES = ["departments", "instructors", "students", "courses", "terms", "sections",
          "enrollments", "grades"]


def _unique_names(rng: np.random.Generator, n: int) -> list[str]:
    combos = [f"{f} {l}" for f in FIRST_NAMES for l in LAST_NAMES]
    idx = rng.choice(len(combos), size=n, replace=False)
    return [combos[i] for i in idx]


def build_rows(seed: int = SEED) -> dict[str, list[tuple]]:
    """Every row of every table, generated from one rng in a fixed order."""
    rng = np.random.default_rng(seed)
    rows: dict[str, list[tuple]] = {t: [] for t in TABLES}

    for i, (name, code, building) in enumerate(DEPARTMENTS, start=1):
        rows["departments"].append((i, name, code, building))
    n_dept = len(DEPARTMENTS)

    inst_names = _unique_names(rng, N_INSTRUCTORS)
    inst_by_dept: dict[int, list[int]] = {d: [] for d in range(1, n_dept + 1)}
    for i, name in enumerate(inst_names, start=1):
        dept = (i - 1) % n_dept + 1          # 5 instructors per department
        rank = RANKS[int(rng.integers(len(RANKS)))]
        hire = int(rng.integers(2004, 2025))
        rows["instructors"].append((i, name, dept, rank, hire))
        inst_by_dept[dept].append(i)

    for i, name in enumerate(_unique_names(rng, N_STUDENTS), start=1):
        dept = int(rng.integers(1, n_dept + 1))
        admit = int(rng.integers(2019, 2026))
        rows["students"].append((i, name, dept, admit))

    course_id = 0
    never_offered: set[int] = set()
    course_dept: dict[int, int] = {}
    for d, (_, code, _) in enumerate(DEPARTMENTS, start=1):
        numbers = sorted(rng.choice(np.arange(100, 500), size=8, replace=False).tolist())
        # One or two courses per department are never scheduled.
        skip = set(rng.choice(8, size=int(rng.integers(1, 3)), replace=False).tolist())
        for k, (num, title) in enumerate(zip(numbers, COURSE_TITLES[code])):
            course_id += 1
            credits = int(rng.choice([1, 2, 3, 3, 4, 4, 5]))
            level = (num // 100) * 100
            rows["courses"].append((course_id, d, code, f"{code} {num}", title,
                                    credits, level))
            course_dept[course_id] = d
            if k in skip:
                never_offered.add(course_id)

    for i, (name, year, season) in enumerate(TERMS, start=1):
        rows["terms"].append((i, name, year, season))

    capacities = [20, 25, 30, 35, 40, 45, 50, 60, 80, 120]
    section_id = 0
    sections_by_term: dict[int, list[tuple[int, int]]] = {}
    for term_id in range(1, len(TERMS) + 1):
        sections_by_term[term_id] = []
        for cid in range(1, course_id + 1):
            if cid in never_offered:
                continue
            roll = rng.random()
            n_sec = 0 if roll < 0.40 else (1 if roll < 0.88 else 2)
            for _ in range(n_sec):
                section_id += 1
                inst = int(rng.choice(inst_by_dept[course_dept[cid]]))
                cap = int(rng.choice(capacities))
                room = f"R{int(rng.integers(100, 400))}"
                rows["sections"].append((section_id, cid, term_id, inst, cap, room))
                sections_by_term[term_id].append((section_id, cid))

    enrollment_id = 0
    ability = rng.normal(0.0, 0.6, size=N_STUDENTS + 1)
    in_progress_id = [t[0] for t in rows["terms"] if t[1] == IN_PROGRESS_TERM][0]
    points_scale = np.array([p for _, p in GRADE_SCALE])
    term_year = {t[0]: t[2] for t in rows["terms"]}
    admit_year = {s[0]: s[3] for s in rows["students"]}
    for sid in range(1, N_STUDENTS + 1):
        for term_id, secs in sections_by_term.items():
            # Students enrol only from their admit year on, and sit some terms out,
            # so per-term headcounts differ instead of always being N_STUDENTS.
            if term_year[term_id] < admit_year[sid] or rng.random() < 0.2:
                continue
            k = int(rng.integers(2, 5))
            order = rng.permutation(len(secs))
            taken_courses: set[int] = set()
            picked = 0
            for j in order:
                sec, cid = secs[j]
                if cid in taken_courses:
                    continue                # never two sections of one course per term
                taken_courses.add(cid)
                enrollment_id += 1
                rows["enrollments"].append((enrollment_id, sid, sec))
                if term_id != in_progress_id:
                    raw = 3.0 + ability[sid] + rng.normal(0.0, 0.7)
                    g = int(np.argmin(np.abs(points_scale - np.clip(raw, 0.0, 4.0))))
                    letter, pts = GRADE_SCALE[g]
                    rows["grades"].append((enrollment_id, letter, pts))
                picked += 1
                if picked == k:
                    break
    return rows


def connect(seed: int = SEED) -> sqlite3.Connection:
    """A fresh in-memory connection loaded with the seeded data."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript(SCHEMA_SQL)
    for table, table_rows in build_rows(seed).items():
        if table_rows:
            marks = ",".join("?" * len(table_rows[0]))
            conn.executemany(f"INSERT INTO {table} VALUES ({marks})", table_rows)
    conn.commit()
    return conn


@lru_cache(maxsize=1)
def shared_connection() -> sqlite3.Connection:
    """One read-only-by-convention connection per process for evaluation."""
    return connect()


def schema_info() -> dict:
    """What a solver may legitimately know: the schema and the entity values.

    Real NL2SQL systems link question words to schema elements and stored
    values, so this is fair game for the system under improvement. It never
    contains questions, gold SQL, or results.
    """
    conn = shared_connection()
    q = lambda sql: [r[0] for r in conn.execute(sql).fetchall()]
    return {
        "tables": {t: [c[1] for c in conn.execute(f"PRAGMA table_info({t})")]
                   for t in TABLES},
        "departments": q("SELECT name FROM departments ORDER BY dept_id"),
        "dept_codes": q("SELECT code FROM departments ORDER BY dept_id"),
        "subjects": sorted(set(q("SELECT subject FROM courses"))),
        "course_codes": q("SELECT code FROM courses ORDER BY course_id"),
        "terms": q("SELECT name FROM terms ORDER BY term_id"),
    }
