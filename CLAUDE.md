# agent-skills

Skills live in `skills/<name>/SKILL.md`. Plugins are entries in `.claude-plugin/marketplace.json` that list skill directories; there is no per-plugin folder or `plugin.json`.

## Writing a skill

- Follow the [Agent Skills spec](https://agentskills.io/specification): `name` matches the directory (lowercase, digits, single hyphens, max 64), `description` 1-1024 characters and says when to use it.
- Frontmatter keys stay portable: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`. Claude Code-only keys (`when_to_use`, `disable-model-invocation`, ...) break other agents and claude.ai uploads.
- Skills are for anyone: no personal names, no paths on one machine, no references to private repos or where an asset came from. Talk about "the user".
- Supporting files (scripts, references, assets) go next to the `SKILL.md` and are referenced by relative path.

## Adding or changing a plugin

- A new skill joins a plugin by adding its directory to that entry's `skills` list. A skill may sit in more than one plugin.
- Entries use `"source": "./"` and `"strict": false`, and carry no `version`, so installs track commits.
- Update the Plugins table in `README.md` in the same change.

## Checks

```bash
python3 .github/scripts/validate_skills.py
claude plugin validate . --strict
```

CI runs both on every pull request.
