# Decisions

One line per judgement call made without asking.

1. Folder is `short_story` at the repo root, lowercase like `assignment1`–`assignment5`.
2. The primary paper is read from arXiv 2510.06445 **v4** (31 Oct 2026, TMLR-published), which is what arXiv serves; v3 (12 Jun 2026, named in the brief) was also downloaded and diffed. v4 is used because it is the peer-reviewed version and revises v3's numbers and one qualitative finding (most-attacked stages).
3. Paper notes keep the paper's seven threat classes (adding red-teaming and interface-level attacks to the five in the brief).
4. Figure 9b's per-class numbers were read from the rendered PDF page (PyMuPDF), because text extraction dropped zero-valued segments.
5. Where the paper quotes one result two ways (MSB 76.5% vs 75.8%, WebInject, VisualTrap), the article will use the figure stated with its condition and note the other.
6. The defense coverage figure will be shaded by paper count (the survey's Fig. 12), labelled as research attention, because the survey states the cells are not effectiveness.
7. PyMuPDF is installed in the venv only to render PDF pages for reading figures; it is not used to produce any output.
