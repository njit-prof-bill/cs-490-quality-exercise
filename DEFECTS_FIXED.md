# Defects Fixed Summary

All defects were found by writing requirement-based tests first (following the
lab workflow), watching them fail, then fixing the implementation.

---

## Level 1 – Core Grading

### CORE-05: Drop-lowest quiz threshold was wrong
**File:** `gradebook/calculator.py` – `_drop_lowest_if_needed`

The lowest quiz was dropped whenever a student had ≥ 2 quiz scores. The policy
requires at least **4 non-excused** quiz scores before any drop occurs. Fixed by
counting only non-excused entries (possible > 0) and raising the threshold to 4.

### CORE-06: Extra credit added average percent instead of earned points
**File:** `gradebook/calculator.py` – `compute_student_grade`

The extra credit branch did `total += average_percent`, which could add up to 100
course-grade points from a single EC assignment. Fixed to `total += earned_points`
(raw points earned), and the final grade is now capped at 100.

### CORE-07 / REPORT-07: Percentages displayed to one decimal place instead of two
**File:** `gradebook/reports.py` – `_format_percent`

`f"{value:.1f}%"` produced `"80.0%"` instead of the required `"80.00%"`. Changed
format string to `:.2f`.

### REPORT-05: Even-count median returned lower middle grade instead of mean
**File:** `gradebook/calculator.py` – `class_median`

For an even number of students the code returned `grades[midpoint - 1]` (the lower
of the two middle grades). Fixed to return `(grades[midpoint - 1] + grades[midpoint]) / 2`.

### CSV-01: Email normalization did not strip whitespace
**File:** `gradebook/students.py` – `normalize_email`

`normalize_email` only called `.lower()`, leaving leading/trailing spaces intact.
A student CSV row like `" erin@njit.edu "` produced a key that never matched grade
rows, so all of Erin's grades were silently ignored. Fixed to `.strip().lower()`.

---

## Level 2 – CSV and Import

### CSV-04: Score-exceeds-max validation was unreachable
**File:** `gradebook/policies.py` – `validate_grade_value`

An early `return issues` guard fired for any score `>= max_points`, so the
`score > max_points` issue was never appended. Removed the premature return and
replaced both conditions with a single correct check that respects
`is_extra_credit`.

### CSV-06: Header-only file produced no validation issue
**File:** `gradebook/importer.py` – `_read_csv_rows`

When a CSV contained only a header row, `rows` was an empty list and the function
returned silently. Added a CSV-06 validation issue when `rows` is empty but
`fieldnames` is not None.

### CSV-07: Malformed student row crashed the importer
**File:** `gradebook/importer.py` – `import_students`

The exception handler ended with `raise`, re-raising the exception instead of
skipping the bad row. Changed `raise` to `continue` so processing continues with
the remaining rows.

---

## Level 3 – Reporting

### REPORT-02: Rankings were sorted ascending; withdrawn students were not excluded
**File:** `gradebook/reports.py` – `build_rank_report`

The sort key `(item.numeric_grade, item.student.email)` sorted grades in ascending
order (lowest first). Changed to `(-item.numeric_grade, item.student.email)` for
descending order. Also the filter excluded `INACTIVE` students instead of
`WITHDRAWN`; fixed to exclude `WITHDRAWN` per STATE-03.

### REPORT-03: Category report averaged raw earned points instead of percentages
**File:** `gradebook/reports.py` – `build_category_report`

`category_scores.append(summary.earned_points)` collected raw point totals and
averaged them, not percentages. Fixed to `summary.average_percent`.

---

## Level 4 – Policy

### POLICY-01: Weight validation double-counted assignments in the same category
**File:** `gradebook/policies.py` – `validate_category_weights`

The function summed `weight` for every assignment individually. Because all
assignments in the same category share one category weight (e.g., three quizzes
each with `weight=0.15` represent a single 15 % category), the sum was inflated.
Fixed to deduplicate by category before summing.

### POLICY-02: Late penalty used max_points instead of earned score; no 3-day cap
**File:** `gradebook/policies.py` – `apply_late_policy`

`score -= assignment.max_points * rate * days_late` deducted a fraction of the
maximum possible score rather than the student's actual earned score, and applied
the penalty for unlimited days. Fixed to `score -= score * rate * min(days_late, 3)`.

### POLICY-04: Pass/fail token check was case-sensitive
**File:** `gradebook/grades.py` – `parse_grade_value`

`token = raw_value.strip()` left the original casing intact, so `"PASS"`,
`"Pass"`, `"FAIL"`, etc. were rejected with `ValueError`. Fixed by adding
`.lower()` before the membership check.

---

## Level 5 – State and Workflow

### STATE-01: InMemoryStorage duplicated data on repeated loads
**File:** `gradebook/storage.py` – `InMemoryStorage.load`

`self.data.grades.extend(…)` and `self.data.validation_issues.extend(…)` were
called on every load, so loading the same files twice doubled the grade and issue
lists. Fixed by replacing the accumulated state with a fresh load each time.

### STATE-04: `validate` command always exited with code 0
**File:** `gradebook/cli.py` – `_handle_validate`

The handler returned `0` unconditionally. Fixed to return `1` when
`data.validation_issues` is non-empty, and `0` otherwise.

### STATE-05: Audit report silently dropped all grade-source issues
**File:** `gradebook/reports.py` – `build_audit_report`

A `if issue.source == "grades": continue` guard filtered out every grade
validation issue (unknown students, invalid scores, etc.). Removed the filter so
all issues appear in the audit output.

### STATE-06: Unknown student status produced no validation issue
**File:** `gradebook/students.py` – `build_student` / `parse_student_status`

An unrecognised status value defaulted to `active` silently. Changed
`parse_student_status` to return an `is_unknown` flag, and `build_student` now
appends a STATE-06 validation issue when that flag is set.

---

## Verification

```
.venv/bin/python -m pytest
75 passed in 0.11s
```
