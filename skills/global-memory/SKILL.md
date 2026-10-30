---
name: global-memory
description: Read and write the user's global memory in ~/.claude/memory/, the cross-project counterpart to per-project auto memory. Use before saving any memory, to decide whether it is global or project-scoped; when a global index line looks relevant and you need the full file; and when the user says "remember this everywhere", "make this a global memory", "move this memory to global", or asks what is in global memory.
---

# Global Memory

Two memory stores, same file format:

| Store | Path | Loaded |
|---|---|---|
| Global | `~/.claude/memory/` | Index imported by `~/.claude/CLAUDE.md`, so every session sees it |
| Project | `~/.claude/projects/<launch-dir>/memory/` | Only in sessions launched from that directory |

Each store has a `MEMORY.md` index (one line per memory) plus one file per fact. Only the index is in context; read a memory file when its index line looks relevant.

## Setup

The global store only works if every session loads its index. If `~/.claude/memory/MEMORY.md` is missing, or `~/.claude/CLAUDE.md` lacks the section below, tell the user and offer to set it up:

1. Create `~/.claude/memory/MEMORY.md` (empty is fine).
2. Add this section to `~/.claude/CLAUDE.md`. The import loads the index into every session; the text tells each session the store exists, since the built-in memory instructions only know the project store:

   ```markdown
   ## Global memory
   Cross-project memories live in `~/.claude/memory/`, alongside the per-project auto memory. Facts that hold across repos go global; only single-repo facts go in project memory. Use the `global-memory` skill (`memory:global-memory` when installed as a plugin) before reading or writing either.

   @~/.claude/memory/MEMORY.md
   ```

## Invoked with no request

Show an overview and stop: one bullet per memory in each store (filename, then its index hook), and flag any index line without a file or file without an index line. Don't ask what to do next.

## Where a memory goes

**Global** when the fact holds regardless of which repo the session started in: how the user wants things done, their tools and machine setup, accounts and environments, workflows that span repos, knowledge about the team or organization.

**Project** only when the fact is about one repo and means nothing elsewhere: a test quirk, a build gotcha, a file layout.

When unsure, go global. A project memory is invisible to every other session.

## Reading

1. Scan the global index (already in context) and the project index.
2. Read the full file for any line that looks relevant to the task.
3. Memories are point-in-time. Verify a file path, flag or command still exists before relying on it.

## Writing

1. Check both indexes for a memory that already covers it, and update that file instead of adding a duplicate.
2. Write one fact per file, named `<type>_<topic>_<fact>.md` (e.g. `feedback_git_annotated_tags.md`). Reuse a topic already in the store when one fits, so related facts sort together, and keep the index sorted by filename:

   ```markdown
   ---
   name: <short-kebab-case-slug>
   description: <one-line summary, used to decide relevance>
   metadata:
     type: user | feedback | project | reference
     modified: <YYYY-MM-DD>
   ---

   <the fact; for feedback/project, follow with **Why:** and **How to apply:** lines>
   ```

3. Link related memories with `[[slug]]`. Slugs resolve across both stores.
4. Add `- [Title](file.md) — hook` to that store's `MEMORY.md`. Keep the line short, since the global index loads in every session.
5. Delete memories that turn out to be wrong, and remove their index line.

## Moving a memory between stores

`mv` the file, then move its index line from one `MEMORY.md` to the other. Slugs don't change, so links keep working.
