# Update when the PR moves

When the user says the code changed or a finding is fixed:

```bash
gh pr view <N> --repo <owner/repo> --json headRefOid,additions,deletions,changedFiles,commits
git -C <clone> fetch -q origin pull/<N>/head
git -C <clone> log --oneline <page-head>..<new-head>
git -C <clone> diff <page-head> <new-head>
```

`<page-head>` is the head sha currently shown on the page. Without a clone, `gh api "repos/<owner>/<repo>/compare/<page-head>...<new-head>"` gives the same delta. Save a fresh `gh pr diff`, because SNIP ranges point into the diff of the head the page shows. Then re-pick the ranges of any snippet whose code moved.

- Edit the existing body, don't rebuild it from scratch, and run `build` again. Within the session that published the page, republish the same file. In a later session, read the artifact by its link (`Artifact` read) and pass the file that comes back to `build` as the body: it takes a page it built before and regenerates the links, the Files list and the dividers. Snippets the delta doesn't touch stay as they are; new or moved ones get SNIP markers into the fresh diff. Publish the result to the same link.
- Change only the sections the delta touches. Then update the meta line's head sha, the rail's `.stat` block and the file chips.
- After a rename, search the page for the old identifiers until none are left.
- Mark fixed findings resolved, or `Accepted risk` when the user accepts one. Never delete a finding silently.
- If the user says a finding is fixed but the delta doesn't fix it, say so and keep it open.
- If a fix creates a new problem, add it as a new note. For example, a test that no longer proves what it claims.

For local changes, see `local-changes.md`.
