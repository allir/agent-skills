---
name: go-style
description: Opinionated Go style for writing and reviewing code, the judgment layer above golangci-lint — error handling (wrap, don't log-and-swallow, sentinels where they're produced), package-level state and dependency wiring, structured logging, whether tests can actually fail, stdlib over hand-rolled loops, and one implementation per concept. Use when writing or changing Go, so the first draft already follows it, and when reviewing Go. Not for defect hunting, generic cleanup of a diff, comment wording, or layout, file splitting and declaration order (go-structure). Use for narrow and yes/no questions too — "is this idiomatic Go?", "review the error handling", "is this test testing anything?", "ErrFoo is defined in one package but returned from another, does that matter?", "every branch should log which path it took", "is there already one of these in the repo?", "clean this up before I commit" — and as the style clause inside a larger Go PR review.
allowed-tools: Read, Glob, Grep, Bash, Edit, Agent
---

# Go Style

Review Go code for the conventions that make a codebase feel like one person wrote it:
how errors travel, where state lives, how things get logged and tested, and whether the
code reaches for the standard library or reinvents it.

This is the judgment layer *above* the linters. Its sibling `go-structure` handles
where code lives — folders, packages, file splitting, declaration order. Defect hunting,
generic diff cleanup and comment wording are out of scope too. Staying in lane keeps the
review useful.

## Fix or report

Report by default. Edit directly only when the user asked for the change — "clean this up
before I commit", "fix the error handling", or writing new code — and then report what
changed, one line per edit.

## Step 1 — Read the linter config, then don't repeat it

Open the golangci-lint config, if there is one, and note what is already enforced. Restating
findings a linter produces on every run is the fastest way to get a review ignored — if
`errcheck`, `errorlint`, `nlreturn`, `usestdlibvars` and `gocritic` are on, unchecked
errors and `%w`-less wrapping are already someone else's job.

Then read `AGENTS.md` or `CLAUDE.md` and `CONTRIBUTING.md`. The repo's documented conventions outrank
everything below. If the repo contradicts this skill, the repo wins; if the repo
contradicts itself, that is the finding.

## Errors

- **Return errors; let the caller decide.** A helper that logs an error and returns `nil`
  has destroyed the caller's ability to react to it, and the log line will be read by
  nobody at 3am. Log-and-swallow in a helper is the highest-value finding in this section.
- **Wrap with context**: `fmt.Errorf("resolving task definition %s: %w", name, err)`. The
  message says what the code was *doing*, lowercase, no trailing punctuation, no "failed
  to" prefix — the chain reads as a sentence, so each link is a clause.
- **Sentinels live in the package that produces them.** `var ErrNotFound = errors.New(…)`
  belongs beside the code that returns it. A shared `errors` package is a `common` package
  wearing a disguise, and it couples every package that touches it.
- **Compare with `errors.Is` / `errors.As`,** never by matching strings. String matching
  breaks silently the day someone improves a message.
- **Render at the edge.** Terminal styling and user-facing phrasing belong in one place at
  the top of the call stack (the repo's error-rendering helper, if it has one), not
  sprinkled through domain code. Domain
  code returns errors; the command layer decides how they look.
- **One error per failure.** Logging an error *and* returning it means it gets reported
  twice, which makes a single failure look like a cascade.

## Package-level state and wiring

Package-level state is justified for **process-immutable data parsed once** — a compiled
regexp, a lookup table, an `embed.FS`, a sentinel error, an HTTP client. `sync.OnceValues`
is the right tool when the parse can fail, since it keeps the error instead of panicking.

It is **not** justified for memoizing a decision. A cached "we already checked whether this
host supports X" is state that outlives the question it answered, cannot be reset in a
test, and produces order-dependent test failures that take a day to diagnose.

Dependencies are parameters, constructed at the top (`main`/`run`) and passed down: a
logger, a client and a clock are three arguments, not three globals. This is the single
biggest determinant of whether Go code is testable, and it is why the codebase can use
hand-written fakes instead of a mocking framework.

Flag a package-level `var` only if something *writes* to it after startup. Immutable
tables are fine, and flagging them trains the user to ignore the review.

## Logging

- **Structured, with fields** — a message plus key/value pairs (`"service", name,
  "region", region`) in whatever form the repo's logger takes, not formatted prose. Fields
  are queryable; sentences are not.
- **Every branch of a selection logs which option it took, and on success only.** When
  code picks between std and bcc, or between a cached and a live path, the log should say
  which one it picked and why. Debugging a support case without that line means guessing.
  Logging the *failure* of a branch that then succeeds elsewhere reads like an incident.
- **The logger is a dependency**, taken as the repo's logger type or a minimal
  package-local `Logger` interface where tests need a stub. Never a package-level global, never a library that
  logs by default — a library logging on its own is deciding something that belongs to the
  program importing it.
- **Levels mean things.** `Debug` for the details you would want in a bug report, `Info`
  for what the program decided, `Warn` for degraded-but-continuing, `Error` for the thing
  that actually stopped. If everything is `Info`, nothing is.

## Tests

- **Table-driven by default.** Once there are three input variations, a table is shorter
  than the copies and makes the missing case obvious. Name subtests after the case, not
  `case1`.
- **A test that skips everywhere, or only logs, is a tool, not a test.** `t.Skip` on every
  platform means the suite is green because nothing ran. A test that calls `t.Logf` and
  never `t.Error` cannot fail. Both are worse than no test, because they show up as
  coverage.
- **Assert on behaviour, not on the shape of the implementation.** Golden files for
  rendered output, `testdata/` for fixtures, `//go:build integration` for anything needing
  real credentials.
- **Fakes are hand-written and live in `_test.go`** — a minimal interface plus a struct
  with the two methods the test needs. They get their own `fakes_test.go` past about four.

## Prefer the standard library

`slices` (`Contains`, `Sort`, `SortFunc`, `Index`, `Equal`), `maps` (`Keys`, `Values`),
`cmp` (`Compare`, `Or`), `min`/`max`, `errors.Join`, `strings.Builder`, `strings.CutPrefix`
— all of these replace loops people still hand-roll out of habit. The hand-rolled version
is not wrong; it is just more code to read and one more place for an off-by-one. The same
goes for test helpers: an in-repo `atoi` or homemade `reverse` duplicates `strconv` and
`slices`, which are already tested.

Same instinct one level up: before adding a dependency, check whether `net/http`,
`encoding/json` or `os/exec` already covers it.

## One implementation per concept

Before writing a parser, a retry loop, a client or a helper, grep the repo — and the
shared modules it already depends on — for an existing one. This is boring advice that catches expensive
problems: kernel-release parsing once existed three times in one repo, each with different
edge-case behaviour, and a 300-line hand-rolled OCI registry client sat inside a cloud
provider file while a shared registry client was already a dependency of a sibling
package.

The cost is not the duplicated lines. It is that the three copies disagree, and the bug
gets fixed in one of them.

When you find a duplicate, say which implementation should survive and why — usually the
shared one, or the one with tests.

## Context and exits

`ctx context.Context` is the first parameter of anything doing I/O; it is never stored in
a struct field. `os.Exit` belongs only in the entry point — anywhere else it silently skips
every `defer`, including the cleanup someone carefully wrote.

## When the review is of a change, not a file

Each commit should build on its own. Data a code change depends on — `go:embed` inputs,
generated files, fixtures — lands in the commit *before* the code that reads it, never
after. A bisect that lands on a non-building commit wastes the afternoon it was supposed
to save.

## Do NOT flag these

- Anything the repo's golangci-lint config already enables.
- Immutable package-level vars: lookup tables, compiled regexps, `embed.FS`, sentinel
  errors, configured HTTP clients.
- Comment wording, verbosity or TMI.
- File length, package layout, folder structure, declaration order — `go-structure`.
- Correctness bugs, race conditions, nil derefs. If you spot one anyway,
  mention it in a single line at the end rather than restructuring the report around it.
- A little duplication *across packages* that buys decoupling. "A little copying is better
  than a little dependency" is real; the target is three copies of one concept inside one
  program, not two packages that each define what they need.

## Report

Group by theme (errors / state / logging / tests / stdlib / duplication), each finding with
`file:line` and the concrete fix, worst first. Close with what you checked and found clean,
so silence reads as coverage. If you have more than about ten findings, rank and cut —
deliver what is worth doing this week.

When the user asked you to *write* Go rather than review it, apply all of the above
silently as you write, and say nothing about it afterwards.

When invoked as a clause inside a bigger PR review, review only the files the PR touches
and report as one section — don't take over the rest of the review.

## Reference

`references/style-rules.md` — the longer form of each rule with worked before/after
examples, the duplication case studies, and which of these rules a linter already covers.
