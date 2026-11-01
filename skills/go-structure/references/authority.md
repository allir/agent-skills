# Which source actually says what

Read this before attributing a structural claim to a source. The single most common
failure in Go structure reviews is quoting an authority that never said the thing.

## The official tier

`go.dev/doc/modules/layout` · Effective Go · Go Code Review Comments ·
`go.dev/blog/package-names` · the Google Go Style Guide.

What they do support:

| Claim | Source |
| ----- | ------ |
| `internal/` for non-exported code; "keep packages in internal as much as possible" | go.dev/doc/modules/layout |
| `cmd/<name>/` for binaries; non-Go top-level dirs permitted | go.dev/doc/modules/layout |
| Import grouping (stdlib / everything else) — the *only* official intra-file ordering rule | Effective Go, goimports |
| "Go style is flexible about file size"; "There is no 'one type, one file' convention" | Google Go Style Guide |
| A maintainer should be able to tell which file holds a given thing | Google Go Style Guide |
| "Avoid uninformative package names like util, utility, common, helper, model, testhelper" | Google Go Style Guide |
| "All top-level exported names must have doc comments" | Google Go Style Guide |
| Interfaces belong in the consuming package; "Do not define interfaces before they are used" | Go Code Review Comments, Google Go Style Guide |
| Package name is part of every call site; avoid stutter | go.dev/blog/package-names |
| `/vN` directory or module path suffix for v2+ | go.dev/blog/v2-go-modules |

## The thing no official source says

**No official Go source prescribes an order for top-level declarations within a file.**
Not "consts, then vars, then types, then funcs". Not "types first". Nothing.

A previous extraction pass invented a Google rule reading "constants, variables, then
types, followed by functions". It does not exist. Google's file guidance is about *focus*
and *reader priority* — important things near the top — never a syntactic sequence.

Two pieces of corroborating evidence that the Go team considers this the author's call:

- `gofmt` and `gofumpt` deliberately never reorder top-level declarations, though they
  reorder plenty else.
- `decorder`, the one linter that *can* enforce an order, ships with the check **disabled
  by default**. The ecosystem built the capability and declined to turn it on.

The half of the rule that does have support is the *cohesion* half: a constructor and
methods immediately following their type. That is exactly how `godoc` and pkg.go.dev
render a package — package doc, consts, vars, funcs, then each type with its constructors
and methods nested beneath it. Source that matches rendered docs reads well for the same
reason.

Every ordering finding is therefore `[house]`.

## Linters

**Recommend `funcorder`.** With its defaults it encodes the defensible half: constructor
after its struct, and a struct's exported methods before its unexported ones. It has
nothing to say about const/var/type sequence, which is the part with no backing.

```yaml
linters:
  enable:
    - funcorder
  settings:
    funcorder:
      constructor: true        # constructors immediately after their struct
      struct-method: true      # exported methods before unexported ones
      alphabetical: false      # call order beats alphabetical order for readers
      function: false          # keep off: fights cohesion blocks
```

Leave `function` off, and say why if someone proposes turning it on. It requires every
exported function in the file above every unexported one, so a block's private helpers
would have to move below the next block's exported API — the flat order again, by the
back door.

Roll it out with `--new-from-rev` or a baseline first — on an existing repo it will have
opinions about files nobody wants to touch today.

**Do not recommend `decorder`.** Its `dec-order` default is `[type, const, var, func]`,
which is neither what most repos do nor what most people mean by "ordered", and its
`init-func-first` check is the opposite of the common "init goes at the bottom, if it
exists at all" preference. Turning it on against a healthy cohesion-block codebase
produces findings against its best files.

Others worth naming when the finding is mechanical: `depguard` (encode the
`cmd/` → `internal/` → domain direction in config instead of prose), `gochecknoinits`
(if the repo wants a hard ban), `gochecknoglobals` (noisy — it cannot tell a lookup table
from mutable state, so prefer a manual check), `revive`'s `file-length-limit` (off by
default, no consensus value — do not enable it).

## The community tier, and where it splits

Agreed, near-universally: start flat and add structure on demand; `internal/` by default;
`main` thin with wiring in `main`/`run`; a package is one responsibility named for what it
provides; no `util`/`common`/`base` and no group-by-kind (`models/`, `services/`,
`controllers/`); consumer-defined interfaces; no package-level mutable state; avoid
`init()`; files split by cohesion with predictive names.

Genuinely contested — present both sides, let the user choose:

| Question | The split |
| -------- | --------- |
| `pkg/` | `golang-standards/project-layout` and large polyglot repos say yes; Russ Cox, Cheney, Bendersky and Edwards say it is noise. Cox opened issue #117 on that repo titled "this is not a standard Go project layout" |
| Domain-first vs pragmatic | Ben Johnson (root package = domain + interfaces up front) vs Ryer/Zien (don't import an architecture; abstract when a second implementation appears) |
| Where interfaces are declared | Consumer-defined (Code Review Comments, Ryer) vs Johnson's root-package domain interfaces |
| Duplication across packages | Cheney and Zien accept it for decoupling ("a little copying is better than a little dependency"); layered/DDD camps extract a shared package |
| Subcommands in `cmd/` | Cobra convention puts subcommand files in `cmd/`; purists say `cmd/` holds only `main` packages and subcommands go in `internal/cli` |
| v2+ | `/v2/` subdirectory (max compatibility) vs tag-only on the main branch (the modern default) |

`golang-standards/project-layout` deserves a fair statement rather than a dunk: its tree is
a menu for a large polyglot repo, not a starting template. Kubernetes and Grafana really do
have `api/`, `build/` and `deployments/` because they have OpenAPI specs, Dockerfiles and
Helm charts. The failure mode is creating fourteen empty directories on day one for a
900-line CLI. Kat Zien, who literally wrote the conference talk on Go app structure,
publicly recanted her own `cmd/`+`pkg/` advice — which is the most honest data point in the
whole debate.

## Sources

- <https://go.dev/doc/modules/layout> · <https://go.dev/doc/effective_go> ·
  <https://go.dev/wiki/CodeReviewComments> · <https://go.dev/blog/package-names> ·
  <https://go.dev/blog/v2-go-modules> · <https://google.github.io/styleguide/go/>
- <https://github.com/golang-standards/project-layout/issues/117> (Russ Cox)
- <https://www.gobeyond.dev/standard-package-layout/> (Ben Johnson)
- <https://grafana.com/blog/how-i-write-http-services-in-go-after-13-years/> (Mat Ryer)
- <https://github.com/katzien/go-structure-examples> ·
  <https://blog.jetbrains.com/go/2023/04/11/catching-up-with-kat-zien-on-the-structure-of-go-apps-in-2023/>
- <https://peter.bourgon.org/go-best-practices-2016/> ·
  <https://peter.bourgon.org/go-for-industrial-programming/>
- <https://eli.thegreenplace.net/2019/simple-go-project-layout-with-modules/>
- <https://dave.cheney.net/2019/01/08/avoid-package-names-like-base-util-or-common> ·
  <https://dave.cheney.net/practical-go/presentations/qcon-china.html>
- <https://rakyll.org/style-packages/> ·
  <https://www.alexedwards.net/blog/11-tips-for-structuring-your-go-projects>
- <https://github.com/golang/go/issues/43731> (proposal: remove `init`)
