# Gantt (estimated working days)
```mermaid
gantt
 title aptx factory plan
 dateFormat YYYY-MM-DD
 section Foundation
 T01 contracts :a1, 2026-11-02, 2d
 T02 foundation :a2, after a1, 3d
 section Core
 T03 downloader :a3, after a2, 6d
 T04 state/cache :a4, after a2, 5d
 T05 APT :a5, after a2, 6d
 T06 privileges :a6, after a5, 4d
 section UX
 T07 CLI/TUI :a7, after a3, 5d
 T08 optimization :a8, after a3, 5d
 section Release
 T09 hardening :a9, after a6, 5d
 T10 verification :a10, after a9, 5d
 T11 packaging :a11, after a10, 3d
 T12 audit :a12, after a11, 2d
```
Dates indicative; update from verified progress.

## Actual checkpoint — 2026-10-30

The estimates above are retained as the original plan. Local implementation and
candidate builds now exist; T09–T12 release evidence remains incomplete. No elapsed
workday estimates are presented as measured completion. See STATUS_REPORT.md.
