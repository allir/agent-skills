# Style rules, long form

Where SKILL.md states a rule, this file shows the shape of the violation and the fix, and
says which rules a linter already covers so the review can skip them.

## Which rules are already automated

If these linters are enabled, do not spend findings on what they catch:

| Linter | Covers |
| ------ | ------ |
| `errcheck` | unchecked error returns, including type assertions |
| `errorlint` | `%v` instead of `%w`, `==` comparison of errors instead of `errors.Is` |
| `nilerr` | returning `nil` after checking `err != nil` — the mechanical half of log-and-swallow |
| `usestdlibvars` | string literals where a stdlib constant exists |
| `gocritic`, `staticcheck` | a broad swathe of hand-rolled-what-stdlib-does |
| `goconst` | repeated string literals wanting a const |
| `dupl` | literal copy-paste duplication (not the semantic kind this skill hunts) |
| `testifylint` | assertion misuse |
| `noctx` | HTTP requests built without a context |
| `exhaustive` | unhandled enum cases in a switch |

What no linter catches, and therefore what this review is *for*: whether an error was
swallowed for a *reason*, whether package state is a cache of a decision, whether every
branch of a selection is observable in the logs, whether a test can fail at all, and
whether this is the third implementation of one idea.

## Errors

**Log-and-swallow.** The mechanical form is caught by `nilerr`; the interesting form is not:

```go
// before — the caller cannot tell this failed, and the log line has no request context
func (c *client) warmCache(ctx context.Context) {
    if err := c.load(ctx); err != nil {
        c.log.Errorw("cache warm failed", "err", err)
    }
}

// after — the caller decides whether a cold cache is fatal
func (c *client) warmCache(ctx context.Context) error {
    if err := c.load(ctx); err != nil {
        return fmt.Errorf("warming cache: %w", err)
    }

    return nil
}
```

If swallowing really is right — a best-effort cleanup, a metric that must not break the
request — say so in one line of comment. The reviewable question is not "did you swallow
it" but "did you decide to".

**Wrapping reads as a sentence.** `fmt.Errorf("patching task definition %s: %w", name, err)`
chains into `patching task definition web: describing service: AccessDenied`. Prefixes like
"failed to" add a word per link and say nothing — by the time a human reads it, the fact
that something failed is established.

**Sentinels.** `ErrNotFound` in the package that returns it, so `errors.Is(err,
store.ErrNotFound)` names its own origin at the call site. A central `internal/errors`
package forces every package to import it and turns one team's error taxonomy into a
project-wide coupling.

## Package-level state

The test for whether package state is acceptable: **could two tests running in either order
disagree about it?** A compiled regexp cannot. A cached "does this kernel support BTF"
absolutely can.

```go
// fine — parsed once, immutable, cannot fail at a surprising time
var semverRe = regexp.MustCompile(`^v?(\d+)\.(\d+)\.(\d+)`)

// fine — parse can fail, so keep the error rather than panicking at import time
var loadPolicy = sync.OnceValues(func() (*Policy, error) {
    return parsePolicy(embeddedPolicy)
})

// not fine — memoizes a decision, invisible to callers, unresettable in tests
var supportsBTF bool
```

A struct field on a value constructed in `main` gives you the same caching with none of the
consequences.

## Logging

The "log which branch you took" rule earns its keep in support cases. When an installer
chooses between two sensor implementations based on kernel capability, the difference
between a five-minute diagnosis and a two-day one is a single line: `"selected sensor"`
with `"type", "std", "reason", "tailored BTF available", "kernel", release`.

Corollary: log the selection **on success only**. Logging "BTF probe failed, falling back"
at `Warn` when the fallback is the normal, correct path on half the fleet teaches everyone
to ignore warnings.

## Tests

**The green-but-empty test.** Two shapes, both of which report as coverage:

```go
func TestThing(t *testing.T) {
    if runtime.GOOS != "linux" { t.Skip("linux only") }   // CI is darwin → never runs
    out := Thing()
    t.Logf("got %v", out)                                  // cannot fail
}
```

If a test needs a real environment, mark it `//go:build integration` and let it be honest
about that, rather than skipping quietly inside the default suite.

**Table shape.** Name the field `name`, run subtests with `t.Run(tt.name, …)`, and put the
expectation next to the input so a reader sees the mapping:

```go
tests := []struct {
    name    string
    in      string
    want    Size
    wantErr bool
}{...}
```

## One implementation per concept — the case studies

- **Kernel release parsing, three times in one repo**, each with different behaviour on
  vendor suffixes. The bug was fixed in one of them.
- **A hand-rolled OCI registry client** (token fetch, manifest resolve, blob URL, tar layer
  extraction — roughly 300 lines) inside a cloud-provider file, while a shared registry
  client was already a dependency of a sibling package in the same module. The structural
  half of this finding (one file holding three concerns) belongs to `go-structure`;
  the duplication half belongs here.

The check is cheap: before writing a helper, grep the module and the shared modules it depends on
for the noun. Thirty seconds against a year of divergence.

## Commits

Data lands before the code that reads it. A commit that adds a `//go:embed` directive for a
file introduced in the *next* commit does not build, and the next person to bisect through
it loses an hour deciding whether their own change broke it.

## Not this skill's job

Comment wording and TMI, layout and file splitting (`go-structure`), defect hunting,
generic diff cleanup, whole-project audits. Findings outside this review's lane get one line,
not a section.
