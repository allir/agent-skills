# Failure-mode grids

Read this when the PR touches one of the things below. For each grid that applies, write the cells out, base against head, before you write the notes; a few examples are not the grid. A cell that turns up a defect becomes a note, tagged by section 5 of SKILL.md.

## Events and messages

For each event, message or callback that writes state, write one row with the columns lost, reordered with each neighbouring event, late and duplicated. Take each failure on its own: a single lost event is the common case, so don't stop at combinations. Note how far the damage spreads and how long it lasts at head compared with base; a new rule can turn a one-off error into one that lasts the rest of the run.

## Caches, maps and dedup keys

- One row per key field: what recycles it (reused ids, inode numbers), what aliases it (symlinks, alternate roots, case, encodings), what truncates it.
- One row per context the key leaves out: the process root, working directory, tenant, version.
- Each way one thing misses its own key.
- How a hit is validated, and when a sibling cache's check actually runs: a check that passes silently on an error validates nothing.

## A new queue, topic, table or endpoint the PR writes to

- What happens when it is missing or unbound, and whether that still counts as success.
- Every override that redirects it, such as a per-tenant host or an alias.
- Retries (duplicates), concurrent workers (ordering), size limits at each hop.
- What the consumer receives, and whether a consumer exists yet.

## Feature flags

On, off, not yet evaluated at startup, provider unreachable after startup, provider disabled, flag missing. A path that fails closed with no fallback loses work in the startup window.

## Mirrored state

For a gauge, status field or cache of a remote resource: each state the source can be in (created, failed, pending, missing, removed outside the system) against each lifecycle event (restart, delete, mode switch).

## User interfaces

What is validated, what is shown and what is submitted are the same copy of the data. What happens when the user acts between updates: a debounce, a pending request, a double click.

