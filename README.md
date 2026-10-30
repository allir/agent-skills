# agent-skills

[Agent Skills](https://agentskills.io) I've written for my own work, shared in case they're useful to you. Every skill is a plain `SKILL.md` under `skills/`, so any agent that supports the standard can use them. For Claude Code, the repo is also a plugin marketplace that bundles them into plugins.

## Install

Pick one route. Using both gives you each skill twice.

### Claude Code plugins

Inside a Claude Code session:

```
/plugin marketplace add allir/agent-skills
/plugin install memory@allir
```

Third-party marketplaces don't auto-update by default. To follow new versions, open `/plugin` → **Marketplaces** → `allir` → **Enable auto-update**. Plugin skills are namespaced, e.g. `memory:global-memory`.

### Any agent: `npx skills`

With the [`skills` CLI](https://github.com/vercel-labs/skills), which supports Claude Code, Cursor, Codex and others:

```bash
npx skills add allir/agent-skills                        # pick from a list
npx skills add allir/agent-skills --skill global-memory  # one skill
```

## Plugins

| Plugin | Skills | What it's for |
| --- | --- | --- |
| `memory` | [`global-memory`](skills/global-memory/SKILL.md) | A cross-project memory store every session loads, next to Claude Code's per-project auto memory: where a memory belongs, the file format, and the one-time setup |

## License

[Apache-2.0](LICENSE)
