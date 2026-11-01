# Extracting house conventions

Step 1 of the review asks for the repo's conventions before judging anything. This is
what that pass should produce: a short list of conventions the repo actually follows,
derived from the code rather than from a blog post.

## Where to look first

A repo that has already written its conventions down usually keeps them in `AGENTS.md`,
`CLAUDE.md` or `CONTRIBUTING.md`. Read those, then check a few claims against the
code — a documented convention the code ignores is itself a finding.

## What to extract when nothing is written down

Skim three or four sibling packages and note what repeats:

| Look at | What a convention looks like |
| ------- | ---------------------------- |
| Filenames across siblings | The same vocabulary everywhere (`config.go`, `run.go`, `render.go`), so a name predicts its contents. The most reusable convention a repo can have |
| Entrypoints | One signature repeated across domain packages, e.g. `Run(ctx, *Config, logger) error` |
| Command packages | What each exports, how subcommands are constructed and registered, one file per subcommand or not |
| Declaration order | Cohesion blocks or flat category order — count, don't assume |
| Flags and config | Where flag-name consts live, how raw flag values become domain types |
| Build constraints | Whether tagged file pairs are complete, including tests |
| Tests | Table-driven or not, fakes vs a mocking framework, where fakes live |
| Generics, generated code, `go:embed` | Where the repo draws the line |

Measure where it is cheap. "Most files interleave types and funcs" is an opinion;
"55% of the files where the two readings differ interleave" settles an argument.

## Calibration

From one mature Go CLI (~380 files, ~57k lines): file length median 93, p75 176, p90 335;
one justified `init()`; no package-level mutable state; every tagged file paired. Use
these as a sense of scale, not as thresholds.
