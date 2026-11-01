# Reviewing a library, not a binary

A library's structure is a public promise; a CLI's is an internal convenience. That single
difference drives everything below. Refactoring a CLI costs an afternoon; renaming an
exported symbol in a library costs every consumer a version bump.

## What differs

| Dimension | Library | CLI / binary |
| --------- | ------- | ------------ |
| `cmd/` | absent | `cmd/<name>/main.go`, or a root `main.go` for a single binary |
| Root package | **is** the public API; name = last element of the module path | `main`, or a thin entry |
| `internal/` | everything not deliberately exported | can be essentially the whole program |
| API surface | every exported symbol is a compatibility promise | zero promises; refactor freely |
| Versioning | semver is load-bearing; v2+ needs the path suffix | tags are release labels |
| Docs | `doc.go`, `example_test.go` (renders on pkg.go.dev) | `--help`, README, completions |
| Config | **never** read flags or env in library code; take a config struct | flags parsed in `cmd/`, resolved into domain types |
| Logging | accept a logger; never log by default | owns the logger, constructs it in `main` |
| `init()` | occasionally justified (driver registration — `database/sql`, `image/png`) | almost never justified |
| Tests | external `package foo_test` doubles as an API-usability check | `testdata/` golden files, end-to-end invocation tests |

## The library checklist

- **Is the exported surface minimal and intentional?** The default question for every
  exported symbol is "who outside this module calls it?" If the answer is nobody, it should
  be unexported or under `internal/`. A library where everything is exported has not made
  an API decision; it has skipped one.
- **Does any exported signature leak a third-party type?** `func New(c *aws.Config)` makes
  your users depend on that SDK's major version forever. This is the most expensive
  structural mistake a Go library can make, and it is invisible until the dependency
  releases a v2.
- **`doc.go` with a real package comment, and at least one `Example`.** Runnable examples
  render on pkg.go.dev and are compile-checked, so they cannot rot the way README snippets
  do.
- **Does anything in the importable path parse flags, read env vars, log by default, or
  call `os.Exit`?** All four steal decisions that belong to the importing program. `os.Exit`
  also skips every `defer` in the caller.
- **Is `internal/` used at all?** If not, check whether that was a decision or an accident.
- **Module path and major version.** A v2+ module needs the `/v2` suffix in `go.mod` and in
  every import path. Cheap to verify, embarrassing to get wrong, and it breaks consumers
  silently.
- **External test package.** `package foo_test` forces you to consume your own API the way
  a user does. A library whose tests all live in `package foo` has never had its API
  exercised from the outside.
- **Context.** Every exported function that does I/O takes `ctx context.Context` as its
  first parameter. Adding it later is a breaking change, which makes it a structural
  decision rather than a stylistic one.

## Both in one repo

Library at the root or in named subdirectories, binaries under `cmd/`. Review the
`internal/` boundary as the API decision it is: the promises stop there. The most valuable
single check is that the import graph flows `cmd/` → `internal/` → domain with no arrows
pointing back — which `depguard` can enforce mechanically once the direction is agreed.
