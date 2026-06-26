# Defects Fixed Summary

## CORE-02: Letter grade boundaries
Fixed letter grade calculation to use the exact grading-policy boundaries with no upward rounding. The previous implementation rounded numeric grades and only returned A/B/C/D/F.

## CORE-03: Missing assignment handling
Fixed missing non-excused assignments so they count as 0 earned points out of the assignment's possible points instead of being treated like full credit.

## CORE-08: Corrected duplicate grade rows
Fixed duplicate grade handling so the latest grade row for the same student and assignment replaces earlier rows during calculation.

## Verification
Ran the pytest suite successfully.

Result: 12 passed.