---
name: go-structure
description: How Go code is organized, for writing it and reviewing it — package and folder layout (cmd/, internal/, pkg/), package naming, file splitting, declaration order, interface placement, import direction and godoc coverage. Use when writing Go — adding a package, command, provider or file so it lands where and how its siblings do — and when reviewing how Go code is arranged. Not for bugs, error handling, logging, tests or stdlib use (go-style), comment wording, or non-Go code. Use for narrow and yes/no questions too — "cmd/ or internal/?", "should I split this file?", "is there a real rule about declaration order?", "should this const be at the top?", "utils.go is a bad name, what's the fix?", "where should this interface live?", "is this package doing too much?", "does this follow our conventions?" — when turning a CLI package into an importable library, and as the structure clause inside a larger Go PR review.
allowed-tools: Read, Glob, Grep, Bash, Agent
---

# Go Structure Review

Review where Go code lives and how it is arranged. Not what it computes — a structure review that drifts into logic bugs
stops being useful for either.

The failure mode to avoid is a report of thirty findings against working code. A review
that opens with "you have 32 ordering violations" gets switched off before the end of the
week. Aim for the handful of findings a thoughtful colleague would actually raise, each
with a file:line and a concrete fix.

## Label every finding with its authority

Go has far less official guidance on structure than people assume, and conflating house
preference with language idiom is how reviews turn into arguments. Tag each finding:

- `[idiom]` — backed by go.dev, Effective Go, Go Code Review Comments, or the Google Go
  Style Guide.
- `[house]` — this repo's convention, or the reviewer's taste. Waivable without argument.
- `[contested]` — the community genuinely disagrees. Say so and let the user pick.

**Intra-file declaration order has no official source.** Not Effective Go, not Code Review
Comments, not go.dev/doc/modules/layout, not the Google Go Style Guide. The only official
intra-file rule is import grouping. Never cite one of those documents for an ordering
finding — every ordering finding is `[house]`. See `references/authority.md` before
claiming any source says anything.

## Step 1 — Learn the house style before judging it

The repo's own conventions outrank everything in this skill. Read, in this order:
`AGENTS.md` or `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`, the golangci-lint config if
there is one, then skim two or three sibling packages that the user considers good. If they
name an exemplar, read it and review against *that*, not against an abstract ideal.
`references/repo-conventions.md` covers what to extract when nothing is written down.

If the repo documents a convention that contradicts this skill, the repo wins and you say
so in the report. If the repo contradicts *itself*, that inconsistency is the finding.

## Step 2 — Classify the project, then branch

The review is genuinely different for the two shapes, so decide first.

- **CLI / binary**: a `package main` exists (root `main.go` or under `cmd/`), or a CLI
  framework is imported (cobra, urfave/cli, kong, flag in main).
- **Library**: no main package; the module is meant to be imported; the root or named
  subpackages carry the exported API.
- **Both**: library at the root or in named dirs, binaries under `cmd/`. The `internal/`
  boundary *is* the API decision — review it as such.

**CLI review** (details below). **Library review**: read
`references/library-layout.md` — minimal exported surface, no third-party types leaking
into exported signatures, `doc.go` and runnable `Example` functions, no flag parsing, env
reading, logging or `os.Exit` in the importable path, correct `/v2` major-version suffix.

## Step 3 — Layout and packages

Officially supported and rarely wrong: `internal/` for anything not deliberately exported,
`cmd/<name>/` for binaries, and non-Go top-level directories (`examples/`, `scripts/`,
`tools/`) are explicitly permitted — do not flag them.

What to actually look at:

- **`pkg/`** `[contested]`. Russ Cox: "the vast majority of packages in the Go ecosystem do
  not put the importable packages in a pkg subdirectory." If it exists and holds the whole
  program, say `internal/` is the better default and move on — one line, not a campaign.
- **Grab-bag packages** `[idiom]`. `util`, `common`, `base`, `helpers`, `misc`, `types`,
  `shared` — Google's style guide blacklists these by name, and they congeal. The fix is
  usually to move each function to its only caller, or to find the noun hiding in the pile.
  A `utils.go` holding four types with methods is misnamed, not a util file.
- **Granularity**. Both extremes hurt: forty 30-line packages, or one 8,000-line
  `internal/app`. A package should be describable in one sentence and worth importing.
- **Stutter** `[idiom]`. Readers see `pkg.Symbol`: `ecs.ECSClient`, `config.ConfigConfig`,
  `util.NewUtil`.
- **Import direction** — the highest-value check in the whole review. Does anything under
  `internal/` import `cmd/`? Is one package imported by nearly everything? Go forbids
  cycles, so teams route around them by inventing a catch-all — the disease presents as a
  naming problem. `go list -deps` or a grep over import blocks answers this.
- **Command files stay thin** (CLI). Whether subcommands live in `cmd/` (the Cobra
  convention) or `internal/cli` (the purist reading) is `[contested]` — accept either and
  check the invariant underneath: command files parse flags and delegate, and every
  command's logic is reachable and testable without constructing a `cobra.Command`.

## Step 4 — Files

Split by cohesion, name for the concept. The working test, from Google's style guide: a
maintainer should be able to guess which file holds a given thing without opening any of
them. There is no "one type, one file" convention, and Google is explicit that "Go style is
flexible about file size".

So **line count is a symptom, not a rule**. Never report a length as a finding on its own.
Open the long file, list the distinct concerns in it, and report *those* — "this file holds
App Service orchestration, SCM host discovery, and a hand-rolled OCI registry client" is a
finding; "this file is 1,658 lines" is a number. A long file that is one function doing one
thing is fine.

For calibration, a mature Go CLI repo measured: median 93 lines, p75 176, p90 335. Past
~350 lines, open it and ask what concerns it holds. Past ~800, it almost always holds more
than one.

Also check: test files beside their source (`patch.go` / `patch_test.go`), fixtures in
`testdata/`, integration tests behind a build tag, and build-constraint file pairs that are
actually complete (every `_linux.go` has its `!linux` twin, including tests).

## Step 5 — Declarations inside a file

**The rule is cohesion blocks, not a flat category order.** A file is a sequence of blocks.
One block is a type, its constructor, its methods, and the unexported helpers only it uses,
with any `const`/`var` that serves it hoisted to the top of that block. Within a block:
exported API first, then private helpers in call order — the order a reader follows the
logic. This mirrors how pkg.go.dev renders a package, which is why it feels right.

"All consts, then all types, then all funcs" is what a **one-block file** looks like. It is
the degenerate case of this rule, not a competing rule. **A type declared after a function
is normal** — it opens the next block. Do not flag it. In the reference codebase, of the 58
files where the two readings are distinguishable, 55% interleave, including both files the
author considers exemplary. Enforcing flat order would reject the best code in the repo.

What is a finding:

1. **An orphan** — a `const`, `var` or `type` with unrelated code both above *and* below
   it, serving nothing nearby. A concurrency-limit const at line 300 of a 400-line file,
   used by one function further down, belongs at the top of the block that uses it. An
   *exported* const buried mid-file is worse: nobody will find it.
2. **Too many independent blocks** — the file wants to be two files (Step 4).
3. **A constructor or method separated from its type** by unrelated declarations.
4. **`init()`** — every one is a finding to justify or convert, because it runs implicitly,
   cannot return an error, and is untestable. Driver registration and populating build info
   from ldflags are genuinely justified; "setting up some state" is not. If it stays, put it
   at the bottom of the file. Do not adopt a linter that forces it first.

## Step 6 — Interfaces and godoc

Interfaces belong in the **consuming** package, small, defined at the point of use — "do
not define interfaces before they are used" `[idiom]`. The producing package returns
concrete types. A package that defines an interface it also implements, with one
implementation, is usually doing it backwards. The good shape: a `checks` subpackage
declares narrow single-method interfaces it needs, and the parent package's SDK adapter
implements them, so the inner package never imports a cloud SDK.

"All top-level exported names must have doc comments" `[idiom]`. Check the packages that
everything else imports first — a UI or primitives package with undocumented exported
symbols costs more than a leaf package with the same gap.

## Do NOT flag these

A noisy review gets disabled, and these are the usual false positives:

- **A type declared after a func.** Cohesion block. Covered above, repeated because it is
  the single most likely mistake.
- **Package-level `var` that is immutable after startup**: a lookup table, a compiled
  regexp, an `embed.FS`, a sentinel error, a configured `http.Client`. These are not global
  mutable state. Flag a package-level var only if something *writes* to it after startup.
- **A justified `init()`** — one that populates version info from ldflags, or registers a
  driver. Name it as checked-and-fine rather than as a finding.
- **Non-Go top-level directories**, unless they are empty scaffolding created in advance.
- **A long single-purpose function** (a render or `View` function), if it really is one
  thing.
- **Two packages with the same base name** in different subtrees. Worth one line if import
  sites need aliases; never a blocker.
- **Anything the golangci-lint config already enforces.** Restating what a linter catches
  on every run is noise; your value is the judgment above the linters.

## Report

Group findings by severity, each with `file:line`, its authority label, and the fix:

```text
## Structure review — <repo/package>, reviewed as <CLI|library|both>

### Findings
1. [house] internal/foo/bar.go:308 — orphaned const …
   Fix: move to the top of the block that uses it.

### Checked and clean
init() usage (1, justified) · build-tag pairing · filename casing · import direction
```

The "checked and clean" line matters: it tells the user what the review covered, so silence
reads as coverage rather than as an oversight. If you end up with more than about ten
findings, rank them and cut — deliver the ones worth acting on this week.

When invoked as a clause inside a bigger PR review, review only the files the PR touches
and report as one section — don't take over the rest of the review.

## References

- `references/authority.md` — which source actually says what, the linter landscape
  (recommend `funcorder`; do **not** recommend `decorder`), and the contested questions.
  Read before citing any source.
- `references/repo-conventions.md` — what to extract when the repo hasn't written its
  conventions down, and a sense of scale from one mature Go CLI.
- `references/library-layout.md` — the library branch of Step 2.
