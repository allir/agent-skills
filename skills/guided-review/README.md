# guided-review

Turns a GitHub pull request into a page that guides a reviewer through it. The core change comes first, then its consequences, and the supporting changes (plumbing, config, tests) are set apart so the reader knows where they can skim. Changes are grouped by what they do rather than by file, and each group explains why it exists before showing the diff lines that carry the point. Every file chip and snippet links to the exact spot in the PR on GitHub. Review notes come last. When new commits land, the page is updated in place: findings are marked resolved or accepted rather than deleted. It also works on a branch before its PR exists: the same page, without the links to GitHub, rebuilt with them once the PR is open.

## Ask for it

In Claude Code, run `/guided-review 123` (optionally followed by `owner/repo`), or just ask:

- "Guided review of PR 123 in our-org/our-service"
- "Walk me through this PR" (from inside a clone, on the PR's branch)
- "Write up PR 456 so the team can review it"
- "Guided review of my branch before I open the PR"
- "We pushed fixes, update the guide"
- "That finding is fixed now, update the report"

## What you get

- **Header**: the PR link and branch, the title, then state, author, head sha and dependency bumps.
- **Reading-order rail**: a sticky list of the groups that highlights the one you're reading, "Supporting changes" and "Review" labels, a collapsible list of every changed file linked to the group that covers it, with a small pie on each file that fills once all its changed lines are shown, file, commit and `+/−` totals, and a Collapse code switch that folds every snippet so you can read just the explanations.
- **Summary**: why the PR exists and its 3–4 headline changes. When behaviour visibly changes, a table: flag combinations and their effects, before/after for changed metrics or outputs, or old/new for a rewrite.
- **Core groups**: the file chips, what changed and why, then GitHub-style diff snippets, then the consequences and non-obvious details. The snippets are highlighted for Go, Java/Kotlin, TS/JS, Python, shell and YAML, and each has a Copy button and a fold toggle. Every changed line appears once, in the group it belongs to; the lines that don't carry the point start folded. Where a change is about shape (a decorator chain, a mode branch, a lifecycle), a small box-and-arrow diagram drawn in the theme.
- **Supporting groups**: the same, set in a quieter style after the core.
- **Links into the PR**: each file chip opens its file in the PR on GitHub, and each snippet title opens the snippet's first line, where you can comment.
- **Review notes**:
  - **Worth a look**: a verified, likely defect, with its call path and a fix sketch, reproduced with a throwaway test when that's cheap.
  - **Promise gap**: a saving or guarantee the PR states that doesn't reach a path that runs today.
  - **Test gap**: changed behaviour that no test exercises.
  - **Latent**, **CI**, **Nit**, **Known gap**, **Open question** and **Accepted risk**.
  - **Resolved** findings keep their original write-up, with a "✓ Resolved in `<sha>`" footer.

Every page uses a navy theme. It follows the viewer's light or dark theme, has an Auto / Light / Dark toggle, works at phone width, and prints as a clean one-column A4 document.

## Requirements

- The `gh` CLI, authenticated for the PR's repo, and `python3`.
- Optional: a local clone at `$PROJECTS_DIR/<repo>`, so the agent can read code around the diff. If `PROJECTS_DIR` isn't set, the agent asks where the clone is. Without a clone, it reads files at the PR's head sha through `gh api`. To build or run a repro test, it exports the head into a scratch directory with `git archive`. The agent treats your clone as read-only and never checks out, resets or pulls in it.
- Publishing works best with an agent that has an Artifact tool (Claude Code with claude.ai), which gives you a link you can share. Other agents write a self-contained HTML file and open it.

## Permissions

`allowed-tools` pre-approves the read-only steps: `Read`, `Glob`, `Grep`, `gh pr view`, `gh pr diff`, `gh pr checks`, running `python3 -B scripts/assemble.py`, and `git -C <clone>` with `fetch`, `log`, `diff`, `show`, `merge-base`, `ls-files`, `archive` and `grep`, plus `tar -x -C` for unpacking an export. Everything else asks as usual: writing files, `gh api` (it can also write, so it isn't pre-approved), running tests, and publishing.

## Files

| File | What it is |
|---|---|
| `SKILL.md` | The workflow: gather the PR, lay out the page, group the changes into core and supporting tiers, write the snippets, write and verify the review notes, and publish |
| `references/local-changes.md` | Inputs, header and build for a branch that has no PR yet |
| `references/updating.md` | Updating a page after the PR moves or a finding is fixed |
| `references/review-checks.md` | Failure-mode grids for caches, queues, flags, mirrored state and UIs, read when the PR touches one |
| `assets/template.html` | The page shell: theme tokens, layout, diff styling, the syntax highlighter, the rail's scrollspy, and one example of each building block |
| `scripts/flow.py` | Draws `<!--FLOW A -> B : label-->` markers as inline SVG diagrams, laid out left to right, in the theme's colours |
| `scripts/assemble.py` | `index` lists a diff's files and hunk line numbers. `build` expands the body's `<!--SNIP a-b-->` markers into lines copied straight from the diff, so no code is retyped, links chips and snippets to the PR, adds the Files list and the tier dividers, warns about changed files no group covers, and splices the body into the template (`--standalone` for agents without an Artifact tool). It also rebuilds a page it built before |
| `scripts/test_assemble.py` | Tests for both scripts: snippet expansion and its refusals, links and line anchors, coverage, tiers, rebuilds, the active-content guard, and diagram parsing. Run `python3 -B -m unittest test_assemble` from `scripts/` |

To change the look, edit the token blocks at the top of `assets/template.html`. Every new page picks the change up.

## Changing the skill

Keep SKILL.md under about 4,500 words; an addition names the line it replaces. A missed finding becomes a rule only when it recurs on two or more PRs from different stacks and can be written as a procedure (a command or a check), not a principle. Grids for specific kinds of change go in `references/review-checks.md`, not in SKILL.md. Trial a change against an answer key written before the runs, and count false statements on the page as well as misses: the page is read instead of the diff, so precision matters more than recall.
