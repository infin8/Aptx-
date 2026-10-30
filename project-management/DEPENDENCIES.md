# Dependency graph
```mermaid
flowchart LR
 T01-->T02
 T02-->T03
 T02-->T04
 T02-->T05
 T05-->T06
 T03-->T07
 T03-->T08
 T04-->T08
 T06-->T09
 T07-->T09
 T08-->T09
 T09-->T10
 T10-->T11
 T11-->T12
```
Contracts freeze before T03/T04/T05 parallel work. Exclusive file ownership mandatory.
