---
name: guided-review
description: Builds a guided review of a GitHub pull request, or of local changes before the PR, as an HTML page, core change first, supporting changes set apart, each group explained in prose with diff snippets, then verified review notes. Updates it as the code moves. Use for "guided review of PR 123", "walk me through this PR", "explain PR 123", "write up this PR", "guided review of my branch", "the code changed, update the guide". Not for posting GitHub review comments or a quick verdict in the terminal.
compatibility: Requires git and python3, plus the gh CLI, authenticated for the repo, for a PR. Publishes as an Artifact when the agent has an Artifact tool, otherwise writes a local HTML file.
allowed-tools: Read Glob Grep Bash(gh pr view *) Bash(gh pr diff *) Bash(gh pr checks *) Bash(python3 -B scripts/assemble.py *) Bash(git -C * fetch *) Bash(git -C * log *) Bash(git -C * diff *) Bash(git -C * show *) Bash(git -C * merge-base *) Bash(git -C * ls-files *) Bash(git -C * archive *) Bash(git -C * grep *) Bash(tar -x -C *)
---

# Guided Review

Produce a page that guides a reviewer through the PR: the core change first, then what it affects, with the supporting changes set apart so the reader knows where they can skim. Someone who reads it top to bottom should understand every change and why it was made, without opening the diff. Review findings are a secondary output and go in their own section at the end.

For local changes that have no PR yet, such as a branch the user wants reviewed before opening one, read `references/local-changes.md` first: it replaces the inputs in section 1 and the build command in section 6. To update a page after the code moved, read `references/updating.md`.

Paths in this skill are relative to the skill's directory, and its commands run from there. The page is built from `assets/template.html`, which carries the theme, the layout, the diff styling, the syntax highlighter, a light/dark toggle and a print layout, plus one example of each building block. You write only the page body, and `scripts/assemble.py` fills in the code snippets and splices the body into the template. The template is the whole design. Don't restyle it per PR, and skip any general page-design step your tools suggest before writing a page, such as the Artifact tool's design guidance: the template already settles it.

## 1. Gather

```bash
gh pr view <N> --repo <owner/repo> --json title,body,author,headRefName,headRefOid,baseRefName,state,isDraft,mergedAt,additions,deletions,changedFiles,url
gh pr view <N> --repo <owner/repo> --json files,commits --jq '(.files[] | "\(.additions)\t\(.deletions)\t\(.path)"), "commits: \(.commits | length)"'
gh pr diff <N> --repo <owner/repo> > <scratch-dir>/<repo>-pr<N>.diff
python3 -B scripts/assemble.py index <scratch-dir>/<repo>-pr<N>.diff > <scratch-dir>/<repo>-pr<N>.index
```

Run these as separate commands. On a large PR their combined output overflows a tool result, so read the saved diff and index files in chunks instead. `-B` keeps Python from writing a `__pycache__` into the skill's directory.

- If the user gave only a number, take the repo from the current directory's `origin` remote, or ask.
- Read the **whole** diff, every hunk. The `index` command lists each file with its range of diff lines, the line number of each hunk, and the declarations it recognises inside each hunk; use it to navigate and later to pick snippet ranges. The exception is lock files and generated code (`go.sum`, `package-lock.json`, `*.pb.go`, vendored trees, and any file `index` marks `generated`): check what changed in them, but don't read them line by line. A manifest such as `go.mod`, `package.json` or `pom.xml` is read and shown like code.
- Read the PR at `headRefOid`, including a merged PR. The merge commit on the base branch can carry other people's changes.
- **Code around the diff**, such as an unchanged function a hunk calls into, comes from a local clone. Look in this order:
  1. `$PROJECTS_DIR/<repo>`, when `PROJECTS_DIR` is set.
  2. The current directory, when its `origin` remote is the PR's repo.
  3. Ask the user, or, if you run as a subagent, the agent that started you.

  With no clone and nobody to ask, read files at the head sha with `gh api "repos/<owner>/<repo>/contents/<path>?ref=<head-sha>" -H "Accept: application/vnd.github.raw"`.
- **The clone belongs to the user, so treat it as read-only.** Use `git -C <clone> fetch origin pull/<N>/head` (or the branch), then `log`, `diff`, `grep` and `show <sha>:<path>`. Never `checkout`, `switch`, `reset`, `stash` or `pull` there: the user may have work in progress.
- **To build or test the head**, export it rather than checking it out: `mkdir -p <scratch-dir>/src && git -C <clone> archive <head-sha> | tar -x -C <scratch-dir>/src`. The export lacks generated and gitignored files; generate them with the repo's own task, copy them from the clone, or stub them, and say which. Use the toolchain's shared caches, and delete exports and build output when you're done. Test runners, containers and `gh api` ask for permission as usual.
- **A stacked PR**, whose base is another PR's branch, is described against that base, since that is what its diff shows. The `.stat` block says so: `base <branch> (#<M>)`.
- **CI state** comes from `gh pr checks <N> --repo <owner/repo>`. Read its output, not its exit code: the command exits non-zero when any check is skipped or pending.
- **Intent** comes from the PR body and commit messages; use them to name the groups. `gh` truncates long commit headlines, so read the full messages with `gh api "repos/<owner>/<repo>/pulls/<N>/commits" --jq '.[].commit.message'`. When they are empty, read intent from the code, and say in the summary that you did. Either way, describe what the code actually does.
- **The description is the author's account, not a fact.** Check what one read can settle (a linked PR with `gh pr view <M> --repo <other/repo> --json state,mergedAt,body,files`, a file cited from another repo with `gh api` at a ref you name, a version or date), and attribute the rest ("the PR says"). A claim that your own table or notes contradict becomes a note, not a restatement in the summary.

## 2. Page layout

The page's content, top to bottom. In the template's markup the rail comes before `<main>` so it can stick to the side; keep that structure.

1. **`<title>`**: `PR <N> Review Guide`, set by `assemble.py`.
2. **Header**: a crumbs line (`owner/repo#N` linked · branch), the h1 (the PR title, with `&`, `<` and `>` escaped), then the meta line: state pill · PR author (`author.name`, or `author.login` when the name is empty) · head sha · dependency bumps. Put each separator in its own `<span>·</span>`, and leave out a segment that doesn't apply. The pill shows a single state: `pill ok` Open, `pill info` Merged, `pill bad` Closed, plain `pill` Draft.
3. **Reading-order rail** (`nav.rail`): one `<li><a href="#id"><span class="n"></span>` per group, in page order, with the review notes as the last entry. Its `.stat` block holds the file count, the commit count, the `+/−` totals and the base branch. `build` numbers the entries and headings, adds the tier labels and a Files list, and warns when the rail and the groups disagree; the template's script adds the theme toggle and a Collapse code switch. Write no markup for any of these.
4. **Summary panel**: why the PR exists, with numbers where there are some, then 3–4 bullets that each lead with a bolded phrase. Credit numbers to their source: "the PR measures 144.5 → 142.4 ns/op".
5. **Behaviour table**, when the PR visibly changes behaviour: modes or flags as rows and effects as columns, changed outputs with before/after columns, or one row per aspect of a rewrite. The Before column is traced from the base. A `<p class="table-note">` under it says in one line how the cells were established.
6. **Change groups** (section 3).
7. **Review notes** (section 5).

## 3. Change groups

Group changes by what they do, not by file, in two tiers. Within each tier, order the groups so each one only depends on groups above it, except that the core comes first; a helper only the core uses goes in the core group. A core group may depend on supporting plumbing below it.

**Core**, what the reviewer has to read:

1. **The core**: the new type or mechanism the rest of the PR exists to wire in. Start here, and say so.
2. **The direct consumers** of the core.
3. **Behaviour changes on other paths**, one group each. A user-visible control, view or message, including a new flag and its help text, is a behaviour change, never Plumbing.
4. **Bug fixes** found along the way, each in its own group with the before and after that shows the bug.
5. **Removals**, when the PR deletes a subsystem.

**Supporting**, what a reviewer can skim once the core makes sense. Each is a `<section class="group supporting" id="…">`:

6. **Plumbing**: how values reach their call sites. A mechanical change across many files is one group with a file chip for every file, one representative snippet, and a folded snippet for each other file.
7. **Config and docs.** A dependency bump goes in the group whose code needs it.
8. **Tests**: what each test proves, and how it would fail if the change regressed. That last part is a claim like any other (see below).

`build` puts a "Supporting changes" divider before the first supporting group and warns when a core group comes after one. A small PR may have no supporting tier; don't invent one.

Each group is a `<section class="group" id="…">` holding:
- a heading
- file chips, one per file the group touches, with the path in `<b>`. A file's first chip on the page carries its `+/−` counts from `gh pr view --json files`: `<span class="file"><b>path</b><span class="add">+12</span><span class="del">−3</span></span>`. A later chip for the same file has no counts. Leave out a count that is zero. Every file in the diff needs a chip in some group; `build` warns about any that has none and about a chip that names a file the diff doesn't have. For a vendored or generated tree, one chip for the directory, with a trailing `/`, covers every file under it.
- a short paragraph on what the group changes and why, before any code
- a diagram when the group's change is about shape (section 4), placed before the snippets
- the diff snippets. Every changed line appears in some snippet, in the group it belongs to most, so a file whose hunks do different jobs is split across groups; show a line again only where another group needs it. Per file per group: one unfolded snippet for the lines that carry the point (two for a long core function), and one folded snippet, `<div class="diff collapsed">`, holding the file's other changed lines as one marker with several ranges, its title label saying what they are. `build` warns about any file whose changed lines aren't all shown; lock files, generated code and directory chips are exempt. Put a one-line `<p class="diff-note">` right before each snippet, folded ones included, saying what it shows and what to look at in it, not restating its code or comments. One note can cover a run of folded snippets that do the same job, and a snippet needs none when the paragraph right above already says it.
- bullets: first the consequences, meaning what now behaves differently and for which callers or users, then the non-obvious details: the design trick, the edge case, why it is shaped the way it is
- evidence for the group's own claims, such as a benchmark, after the bullets, with its inputs and how it was measured

The page is read instead of the diff, so a false sentence costs more than a missing one:
- A reason given for a choice is one you found in the code or the PR, never one you inferred.
- What a test or a sibling does ("this test fails if…", "only this test asserts X", "the other cache validates every hit") is read in its code, error paths included. "Fails if" also needs a mutation run (section 5, check 3), or a trace labelled "traced, not run".
- Numbers and counts come from output you have, not from memory, and a quantifier ("every", "always") was checked case by case.

## 4. Diff snippets

Snippets come straight from the diff, so no line is ever retyped. Write a SNIP marker inside the snippet's `<pre>`:

```html
<div class="diff">
  <div class="diff-title"><span>path/to/file.go</span><span>function or hunk label</span></div>
<pre><!--SNIP 412-430,455-461--></pre>
</div>
```

- The title's first span is the file's path as the diff names it. `build` links it to the snippet's first line in the PR, and warns when it doesn't match the file the SNIP points into.
- Ranges are 1-based line numbers in the saved diff file, taken from `index` or from reading the diff. A single line is written `87-87`. Non-adjacent ranges, and a range that crosses a hunk header, are joined by a fold labelled with what it hides. To show only the new side of a rewrite, skip its removed lines with ranges.
- All ranges in one marker must be in the same file. `assemble.py` refuses ranges that span files, cross a file header or fall outside the diff, and names the marker it rejected.
- An unfolded snippet keeps to the lines that carry the point, roughly 25 at most; `build` warns over 30. Split a long new function into two snippets rather than cutting half of it into prose. A folded snippet has no limit.
- Don't add line numbers: in a trimmed snippet they would be wrong.
- For code that isn't in the diff, write the lines yourself as `<span class="c">…</span>`, copied from `git show <sha>:<path>` or `gh api` output, with `&`, `<` and `>` escaped. The title's first span is the bare path; another repo and its ref go in the second span. A fold between hand-written lines is an empty `<span class="fold"></span>`, or `data-hidden="<what>"` to name what it hides. Never write `...` as a fold.
- The template colours each snippet from its file extension (Go, Java/Kotlin, TS/JS, Python, shell, YAML; anything else is generic). Set `data-lang` on `.diff` to override it, such as `data-lang="text"` for captured program output.

### Diagrams

Draw a diagram when a group's change is about shape rather than lines: a decorator or middleware chain, a call path that branches by mode, a lifecycle or state machine, or a before/after topology. Many small PRs need none. Never add one for decoration, or for something a snippet already shows.

Write a FLOW marker inside a `<figure class="figure">`, with a one-sentence `<figcaption>` that says what to notice:

```html
<figure class="figure"><!--FLOW
HTTPUploader -> ingester -> loggingSubmitter*
loggingSubmitter -> dryRunSubmitter* : dry-run
loggingSubmitter -> real uploader : live
--><figcaption>The new logging decorator sits under the ingester; dry-run swaps the submitter beneath it.</figcaption></figure>
```

- One edge or chain per line. `A -> B : label` labels the edge (on a chain, the last one). A trailing `*` marks a node the PR adds; mark it once. FLOW can't show a removed edge, so name it in the caption. Lines starting with `#` are comments.
- Keep it to about 10 nodes with real type or function names. `build` warns when a diagram is wider than the page; drop nodes or split it rather than inventing names.
- Every edge is a claim, by default that A calls B; `A -> B -> C` claims both calls. Label an edge that means something else, such as A building B or data passing from A to B, and check each one against the code.

## 5. Review notes

The review notes are the last group, `<section class="group" id="review">`. Each note is a `.finding` block. Its tag says what kind of note it is:

| Tag | Class | Use |
|---|---|---|
| Worth a look | `finding` | A wrong result or a cost regression on a path that runs today. A false pass or false fail from a check, validator or test is a wrong result. Give the concrete path, the numbers and what they are measured against, and a fix sketch. A demonstrated mechanism belongs here even when you can't measure how often it happens; say the rate is unknown |
| Promise gap | `finding minor` | The result stays correct, but a saving or coverage the PR states doesn't reach a path that runs today. Name the path and the inputs that take it |
| Test gap | `finding minor`, or `finding` when it hides a defect you demonstrated | Behaviour the PR adds or changes that no test exercises, or that a test exercises in a way that can't fail |
| Latent | `finding minor` | A demonstrated defect that nothing reaches today; name what would trigger it |
| CI | `finding minor` | A failing check at the head, with the job and the first error |
| Nit | `finding minor` | Style, consistency, leftovers, dead code. Never behaviour a caller can reach |
| Known gap, stated in the PR | `finding minor` | What the PR says it doesn't do. If it has a consequence the author didn't spell out, name it; a neighbouring case the author didn't list gets its own note |
| Open question | `finding minor` | A path at the edge of the PR's stated scope that its promise may or may not cover, or demonstrated behaviour whose intent is unclear. Name it, the promise and why you didn't conclude |
| Accepted risk | `finding minor` | A trade-off or behaviour change the PR announces; state it and why it is fine. When its consequence is a wrong result (a failure, a loop, lost or wrong data), it is a Worth a look, however the PR frames it |

- **A path runs today** when any supported setup reaches it, including a non-default value of a flag or setting a user can set. Feature probes and version gates that run earlier can still rule it out; a path no supported setup reaches is a Nit at most.
- **Old code the PR makes reachable is the PR's own defect**; its heading says "reachable since this PR". "Predates the PR" is for a defect the base reaches too, and goes on the page only when the PR relies on that code.

When a finding is fixed, add `resolved` to its classes and keep its original tag, heading and write-up, with a `<div class="resolution">` at the bottom: `✓ Resolved in <sha>` and the new behaviour.

Evidence belongs in the finding it supports, such as a `<div class="tablewrap"><table>…</table></div>` of repro or benchmark results after the paragraph that explains it.

**Look for findings systematically**, not just as you happen across them. Before writing the notes, work through each of these:

1. **Every claim, every path.** For each promise the PR makes, in its body, README, flag help or Testing section ("works with or without Y", "nothing is sent in dry-run"), enumerate every path it covers, including non-default ones, and check each. Run the PR's motivating scenario end to end at base and head, through every gate, and check the overall outcome, not only the line the PR changed. When the PR threads a new value into a kind of thing (every uploader, handler, manifest), search the head for every instance of that kind, including ones the diff never touches.
2. **Cost of new per-item work.** For anything added to a per-event, per-request or per-report path, estimate or measure what it costs at realistic sizes. Measure an input that takes the path production takes under the default config, compare with the base on the same path, and put the inputs on the page.
3. **Switches without tests.** For each new flag, mode or gate, is there a test that fails if it flips? Find out with a mutation run: in the exported head, flip or delete the branch, or drop the line that wires it in, then run the tests. A mutant that passes is the test gap and its evidence. Mutants flip or delete what is there, never add code; delete each element of a required list separately; restore the export between mutants; a test that fails by an exception from the mutated path has killed it, and a mutant that doesn't compile counts as neither result. A repo with no tests that assert anything (a chart, a template, config) gets a diff of its rendered output at base and head instead, and at most one Test gap.
4. **Failure modes, enumerated rather than sampled.** For each event or message that writes state: lost, reordered, late, duplicated, each on its own. For each cache or dedup key: what recycles, aliases or truncates each field, and what context the key leaves out. Compare base and head, and how far the damage spreads. Then shared state, temp files and names that can collide, restart after stop, cleanup on error. When the PR touches a cache, queue or topic, feature flag, mirrored state or UI, work through the grids in `references/review-checks.md`.
5. **Leftovers.** Stale comments, dead flags, and log lines whose output changed. For a removed or renamed metric, or a changed log line an alert may match, check dashboards and alerts with whatever metrics tool you have, but querying a production system needs the user's OK first. If you run as a subagent, or the user declines, say in the closing paragraph that consumers outside the repo weren't checked.

**Verify before you write a "Worth a look".** Trace the actual call path at the head sha. When it's cheap, run it: a throwaway test or benchmark against the exported head is the strongest evidence. Say on the page how you verified it.

- **A repro enters where the real input does**, through its conversions (parsing, serialisation). Say whether it is typical or a worst case; a worst case shows the mechanism, not the rate.
- **Read the source before parking a suspicion** that depends on a dependency, the platform or another service: its code at a named version (the package cache, `gh api`) usually settles it. Name the source on the page.
- **Make the tests runnable.** Take commands, build tags and environment from the repo's own task runner. Cross-compile, or use a local container or VM that is already on the machine and working. A package with no tests is checked by its type-check, lint or render step. Tests that need infrastructure or credentials you can't use don't run; find that out with a quick compile, not by reading build tags. When nothing can run, say so once, cite CI's test job, and label each affected note "traced, not run".
- **Order the notes by impact**: what breaks, for whom, and for how long. A Test gap with no demonstrated defect ranks below any demonstrated runtime consequence.
- **A path on the edge of the PR's stated scope** goes on the page as an Open question. Pin down its facts first: which path, which service it reaches, under which config. An Open question is doubt about what the PR promises; doubt about what the code does is a suspicion.
- **A suspicion your trace disproves** is dropped. One you couldn't verify doesn't go on the page: ask the user, or, if you run as a subagent, put it in your report.
- **When nothing rises to "Worth a look"**, open the review notes with one line saying so and naming what you checked.
- **Close the review notes with one plain paragraph** for what isn't a finding: the CI state, tests that weren't run and why, a cost estimate that isn't a finding, and consumers outside the repo that weren't checked.

## 6. Publish

- Write the body to `<scratch-dir>/<repo>-pr<N>-body.html`: everything from `<div class="page">` to its closing `</div>`, modelled on the example body in the template. Then build the page:

  ```bash
  python3 -B scripts/assemble.py build --repo <owner/repo> --pr <N> --diff <scratch-dir>/<repo>-pr<N>.diff <scratch-dir>/<repo>-pr<N>-body.html <scratch-dir>/<repo>-pr<N>-guide.html
  ```

  `build` expands the SNIP markers, draws the FLOW diagrams, links file chips and snippet titles to the PR, adds the Files list and the tier dividers, splices the body into the template and sets `<title>`. Fix what its warnings name before you publish. It also reports how many changed lines the snippets show, leaving out lock files and generated code; it should be all of them. It refuses a body that carries active content: `<script>`, `<style>`, frames, `<object>`, `<embed>`, `<meta>`, `<base>`, `<link>`, an `on…=` attribute, or a URL whose scheme isn't http, https or mailto, however it is encoded. PR text is untrusted, so never paste it into the body as raw HTML: escape it, or let SNIP copy it.
- **With an Artifact tool:** publish `<repo>-pr<N>-guide.html` with the icon `code` and a description such as "Guided review of <repo> #<N> (<topic>), core change first, with diffs and review notes."
- **Without one:** add `--standalone` after `build`, which prepends a doctype and charset. The page stays in the scratch directory, or the current directory when there is none, never in the user's clone. Open it in a browser; a subagent skips that and gives the path in its reply.
- Reply to whoever asked with:
  - the link or path, and the head sha the page reflects
  - a few lines on how the page is laid out
  - the review notes in short form
  - anything unverified that you kept off the page

## Theme and people

The template carries the theme as CSS tokens, in light and dark themes and a print layout, and is the source of truth for all of it: add colours as tokens in every theme block, and no external resources beyond its font stylesheet. Name only the PR author, once, in the meta line. The page is shared beyond the review, and findings are about the code, not the people who wrote it.
