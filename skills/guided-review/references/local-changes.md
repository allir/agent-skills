# Local changes, before a PR

When the user asks about a branch or their working copy rather than a PR, the repo is the user's working copy, which stays read-only like any clone. Run `git -C <repo>` from anywhere; the paths it prints are relative to the repo root. Everything in SKILL.md applies except what this file replaces.

## Inputs

- **Base:** the merge base with the default branch, `git -C <repo> merge-base origin/<default> HEAD`. Take the default branch from `git -C <repo> symbolic-ref --short refs/remotes/origin/HEAD`, or use the base the user names. Branched off another branch? Ask which one to compare against.
- **Diff:** what the PR would carry if it were opened now: the branch's commits plus uncommitted changes to tracked files. Diff the working tree against the base, with flags that keep the output in the format `build` reads whatever the user's git config says:

  ```bash
  git -C <repo> diff --no-color --no-ext-diff --src-prefix=a/ --dst-prefix=b/ <base> > <scratch-dir>/<name>.diff
  git -C <repo> diff --no-ext-diff --numstat <base>
  ```

  `<name>` is `<repo-name>-<branch>`, with `/` replaced by `-`. The `--numstat` output gives the file chips' `+/−` counts. Diff `<base> HEAD` instead only when the user asks for the committed state. Untracked files aren't in either diff. List them with `git -C <repo> ls-files --others --exclude-standard`, and when they belong to the change, append each one with `git -C <repo> diff --no-index --no-color --src-prefix=a/ --dst-prefix=b/ /dev/null <path> >> <scratch-dir>/<name>.diff` (it exits 1 when it writes a diff, which is not an error). Then run `index` on the saved diff as for a PR.
- **Intent** comes from `git -C <repo> log --format='%H%n%B' <base>..HEAD` and from what the user says the change is for. There is often no description yet, so read intent from the code and say in the summary that you did.
- **To build or test**, export `HEAD` as for a PR, then apply the uncommitted changes to the export: `git -C <repo> diff --binary HEAD > <scratch-dir>/wip.patch` and `git apply <scratch-dir>/wip.patch` from inside the export. Copy any untracked files the diff includes.
- **No CI has run.** Say so in the closing paragraph of the review notes, along with the tests you ran.

## Header

- `<title>` is `<branch> Review Guide`, set by `build`.
- The crumbs are `owner/repo` (unlinked) · branch.
- The h1 says what the change does, in the style of a PR title.
- The pill is a plain `pill` reading Local, and the author is the commits' author.
- The head sha is followed by "+ uncommitted changes" when the diff includes them.

## Build

Leave out `--repo` and `--pr` and name the page after the branch. Nothing is linked, since there is no PR to link into:

```bash
python3 -B scripts/assemble.py build --name <branch> --diff <scratch-dir>/<name>.diff <scratch-dir>/<name>-body.html <scratch-dir>/<name>-guide.html
```

## Updating

Save a fresh diff against the same base, re-pick the ranges of snippets whose code moved, and rebuild. Once the PR exists, switch to the PR's own diff and add `--repo` and `--pr`. The two diffs number their lines differently, so re-pick every SNIP range. The rebuild then links the page to the PR, and the header becomes the PR's.
