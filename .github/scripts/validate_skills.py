"""Check every skills/*/SKILL.md against the Agent Skills spec (https://agentskills.io/specification)."""

import re
import sys
from pathlib import Path

NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    keys = {}
    for line in m.group(1).splitlines():
        if line and not line[0].isspace() and ":" in line:
            key, _, value = line.partition(":")
            keys[key.strip()] = value.strip().strip('"')
    return keys


def check(path):
    errors = []
    fm = frontmatter(path.read_text())
    if fm is None:
        return [f"{path}: no YAML frontmatter"]
    name, desc = fm.get("name", ""), fm.get("description", "")
    if not NAME.match(name) or len(name) > 64:
        errors.append(f"{path}: name {name!r} must be 1-64 lowercase letters, digits and single hyphens")
    if name != path.parent.name:
        errors.append(f"{path}: name {name!r} must match its directory {path.parent.name!r}")
    if not 1 <= len(desc) <= 1024:
        errors.append(f"{path}: description must be 1-1024 characters")
    for key in sorted(set(fm) - ALLOWED):
        errors.append(f"{path}: {key!r} is not portable (allowed: {', '.join(sorted(ALLOWED))})")
    return errors


def main():
    skills = sorted(Path("skills").glob("*/SKILL.md"))
    errors = [e for p in skills for e in check(p)]
    for e in errors:
        print(e)
    print(f"{len(skills)} skills, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
