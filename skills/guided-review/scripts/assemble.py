#!/usr/bin/env python3
"""Build a guided review page from a body file and the PR diff.

    python3 -B scripts/assemble.py index svc-pr123.diff
        Lists every file in the diff with the diff line numbers of its hunks, for picking snippet ranges.

    python3 -B scripts/assemble.py build --repo owner/repo --pr 123 --diff svc-pr123.diff body.html svc-pr123-guide.html
        Expands each <!--SNIP a-b,c-d--> marker in the body into diff lines, links file chips and snippet
        titles to the PR on GitHub, adds the rail's file list and the supporting-changes dividers, then
        splices the body into assets/template.html and sets <title>. The body may also be a page this
        command built earlier; what it generated is regenerated. --standalone prepends a doctype for agents
        without an Artifact tool.

    python3 -B scripts/assemble.py build --name feat/x --diff local.diff body.html feat-x-guide.html
        The same for changes that have no PR yet: nothing is linked, and <title> is "<name> Review Guide".

A SNIP marker goes inside a snippet's <pre>. Its ranges are 1-based line numbers in the diff file, all
in one file of the diff. A fold is placed between non-adjacent ranges and wherever a range crosses a
hunk header.

A FLOW marker goes inside a <figure class="figure"> and is drawn as an inline SVG diagram; see
scripts/flow.py for its syntax.
"""
import argparse
import hashlib
import html
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import flow

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template.html"
DOCUMENT_HEAD = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                 '<meta name="viewport" content="width=device-width, initial-scale=1">\n')
SNIP = re.compile(r"<!--SNIP ([0-9,\s-]+)-->")
FLOW = re.compile(r"<!--FLOW\b(.*?)-->", re.S)
HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
CHIP = re.compile(r'<span class="file"><b>([^<]+)</b>')
GH_LINK = re.compile(r'<a class="gh" [^>]*>([^<]*)</a>')
DIFF_TITLE = re.compile(r'(<div class="diff-title"><span>)([^<]*|<a class="gh" [^>]*>[^<]*</a>)'
                        r'(</span>.*?</div>\s*<pre>(?:<!--SNIP ([0-9,\s-]+)-->)?)', re.S)
GROUP = re.compile(r'<section class="group( supporting)?" id="([^"]+)"')
RAIL_ITEM = re.compile(r'<li><a href="#([^"]+)"><span class="n">[^<]*</span>')
GROUP_NUMBER = re.compile(r'(<div class="group-head"><span class="n">)[^<]*(</span>)')
SNIPPET = re.compile(r'<div class="diff-title"><span>(.*?)</span>.*?</div>\s*<pre>(.*?)</pre>', re.S)
SNIPPET_OPEN = re.compile(r'<div class="(diff(?: [^"]*)?)"')
SNIPPET_LINE = re.compile(r'<span class="([ad])">(.*?)</span>')
SIGN = {"a": "+", "d": "-"}
LOCK_OR_GENERATED = re.compile(r"(^|/)(go\.sum|package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|"
                               r"Cargo\.lock|poetry\.lock|uv\.lock|Gemfile\.lock|composer\.lock)$|"
                               r"\.pb\.go$|_pb2\.py$|[._]generated\.")
GENERATED = [
    (re.compile(r'(<span class="file">)<a class="gh" [^>]*>(<b>[^<]*</b>)</a>'), r"\1\2"),
    (re.compile(r'<details class="files-index">.*?</details>\s*', re.S), ""),
    (re.compile(r'<li class="tier">.*?</li>\s*'), ""),
    (re.compile(r'<p class="eyebrow tier">.*?</p>\s*'), ""),
]
KIND = {" ": "c", "-": "d", "+": "a"}
FOLD = '<span class="fold"></span>'
HIDDEN = {"+": "added", "-": "removed"}
LONG_SNIPPET = 30
TIER_LABEL = "Supporting changes"
REVIEW_LABEL = "Review"
GENERATED_HEADER = re.compile(r"DO NOT EDIT|@generated|GENERATED CODE|[Aa]uto-?generated|AUTO-?GENERATED")
LANDMARK = re.compile(r"""^[+ ]\s*(?:
    func\s | (?:async\s)?def\s | class\s | function\s | fun\s | type\s\w+\s(?:struct|interface)
  | (?:pub(?:\(\w+\))?\s)?(?:fn|impl|struct|enum|trait)\s
  | (?:(?:export|default|public|private|protected|internal|static|override|abstract|async)\s)+
      (?:function|class|interface|fun|enum|record|type\s\w+|(?:[\w.<>\[\],?]+\s+)*\w+\s*(?:<[^>]*>)?\()
  | (?:export\s)?(?:declare\s)?(?:interface\s\w+|type\s\w+.*=)
  | (?:export\s)?(?:const|let|var)\s\w+(?:\s*:\s*[^=]+)?\s*=\s*(?:async\s+)?
      (?:function\b|\([^)]*\)\s*(?::\s*[^=]+)?=>|\(\s*\{?\s*$|\w+\s*=>)
  | (?!(?:if|for|while|switch|catch|return|else|do)\b)\w+\s*\([^)]*\)\s*(?::\s*[^{]+)?\{\s*$
)""", re.X)
ACTIVE = re.compile(r"<\s*/?\s*(?:script|style|iframe|object|embed)\b|<[^>]*\son\w+\s*=", re.I)
ACTIVE_TAGS = {"script", "style", "iframe", "frame", "object", "embed", "applet", "meta", "base", "link", "animate", "set"}
URL_ATTRS = {"href", "src", "action", "formaction", "xlink:href", "poster", "background", "cite"}
SAFE_SCHEMES = {"http", "https", "mailto"}
URL_SCHEME = re.compile(r"([a-z][a-z0-9+.-]*):", re.I)
URL_IGNORED = re.compile(r"[\x00-\x20\x7f]")


class SnipError(Exception):
    pass


class ActiveContent(HTMLParser):
    """Finds active content the way a browser reads it: attribute values unescaped, and the whitespace and
    control characters a browser drops from a URL dropped before its scheme is read."""

    def __init__(self):
        super().__init__()
        self.found = None

    def handle_starttag(self, tag, attrs):
        if self.found:
            return
        if tag in ACTIVE_TAGS:
            self.found = f"<{tag}>"
            return
        for name, value in attrs:
            scheme = URL_SCHEME.match(URL_IGNORED.sub("", value or ""))
            unsafe_url = name in URL_ATTRS and scheme and scheme[1].lower() not in SAFE_SCHEMES
            if name.startswith("on") or unsafe_url:
                self.found = f"{name}={value!r} on <{tag}>"
                return


def read_lines(path):
    return path.read_text(encoding="utf-8", errors="replace").removesuffix("\n").split("\n")


def header_of(diff, n):
    """The 1-based line number of the file header that diff line n belongs to."""
    for i in range(n - 1, -1, -1):
        if diff[i].startswith("diff --git "):
            return i + 1
    raise SnipError(f"diff line {n} is before the first file header")


def path_at(diff, header):
    """The path of the file whose header is at diff line `header`: the +++ side, or --- for a deletion."""
    old = None
    for line in diff[header:]:
        if line.startswith(("diff --git ", "@@")):
            break
        if line.startswith("+++ ") and line != "+++ /dev/null":
            return line[4:].removeprefix("b/")
        if line.startswith("--- ") and line != "--- /dev/null":
            old = line[4:].removeprefix("a/")
    return old or diff[header - 1].split(" b/", 1)[-1]


def hunk_mask(diff):
    """True for each diff line that sits inside a hunk, so file headers between hunks read as False."""
    mask, inside = [], False
    for line in diff:
        if line.startswith("diff --git "):
            inside = False
        elif line.startswith("@@"):
            inside = True
        mask.append(inside)
    return mask


def diff_files(diff):
    """Each file in the diff: its path, header line, hunks as (line, text), last line, +/- counts, and whether
    its header comment marks it as generated."""
    files = []
    for n, line in enumerate(diff, 1):
        if line.startswith("diff --git "):
            files.append({"path": path_at(diff, n), "header": n, "hunks": [], "adds": 0, "dels": 0})
        elif not files:
            continue
        elif line.startswith("@@"):
            files[-1]["hunks"].append((n, line))
        elif files[-1]["hunks"] and line[:1] == "+":
            files[-1]["adds"] += 1
        elif files[-1]["hunks"] and line[:1] == "-":
            files[-1]["dels"] += 1
    for i, f in enumerate(files):
        f["last"] = files[i + 1]["header"] - 1 if i + 1 < len(files) else len(diff)
        f["generated"] = is_generated(diff, f)
    return files


def is_generated(diff, f):
    """True when the file's first lines carry a generated-code header, which only shows when a hunk starts at line 1."""
    if not f["hunks"] or (HUNK.match(f["hunks"][0][1]) or [None] * 3)[2] != "1":
        return False
    start = f["hunks"][0][0]
    top = [line for line in diff[start:f["last"]] if line[:1] in "+ "][:10]
    return any(GENERATED_HEADER.search(line) for line in top)


def line_anchor(diff, n):
    """GitHub's anchor for diff line n, or the first code line after a hunk header: R<new>, or L<old> for a removal."""
    target = n + 1 if diff[n - 1].startswith("@@") else n
    start = target - 1
    while start >= 1 and not diff[start - 1].startswith("@@"):
        if diff[start - 1].startswith("diff --git "):
            return None
        start -= 1
    if start < 1 or target > len(diff):
        return None
    match = HUNK.match(diff[start - 1])
    if not match:
        return None
    old, new = int(match[1]), int(match[2])
    for k in range(start + 1, target):
        kind = diff[k - 1][:1]
        if kind in (" ", ""):
            old, new = old + 1, new + 1
        elif kind == "-":
            old += 1
        elif kind == "+":
            new += 1
    kind = diff[target - 1][:1]
    if kind == "-":
        return f"L{old}"
    if kind in ("+", " ", ""):
        return f"R{new}"
    return None


def render(diff, in_hunk, spec, notes):
    ranges = []
    for part in spec.replace(" ", "").split(","):
        try:
            start, end = (int(x) for x in part.split("-"))
        except ValueError:
            raise SnipError(f"bad range {part!r}; write it as a-b") from None
        if start > end:
            raise SnipError(f"range {part} is backwards; write it as a-b")
        if start < 1 or end > len(diff):
            raise SnipError(f"range {part} is outside the diff (1-{len(diff)})")
        trimmed = end
        while trimmed > start and not in_hunk[trimmed - 1]:
            trimmed -= 1
        if trimmed != end:
            notes.append(f"range {part} ends past its file; trimmed to {start}-{trimmed}")
        ranges.append((start, trimmed))

    headers = {header_of(diff, start) for start, _ in ranges}
    if len(headers) > 1:
        names = sorted(path_at(diff, h) for h in headers)
        raise SnipError(f"ranges {spec} span several files: {', '.join(names)}")

    out = []
    prev_end = 0
    for start, end in ranges:
        if prev_end and start != prev_end + 1 and not is_fold(out):
            out.append(fold_over(diff[prev_end:start - 1]))
        prev_end = end
        for n in range(start, end + 1):
            line = diff[n - 1]
            if not in_hunk[n - 1]:
                raise SnipError(f"range {start}-{end} runs into a file header at diff line {n}: {line[:60]!r}")
            if line.startswith("@@"):
                if out and not is_fold(out):
                    out.append(FOLD)
                continue
            if line.startswith("\\"):
                continue
            kind = KIND.get(line[:1])
            if kind is None:
                if line == "":
                    kind, line = "c", " "
                else:
                    raise SnipError(f"diff line {n} is not a hunk line: {line[:60]!r}")
            out.append(f'<span class="{kind}">{html.escape(line[1:], quote=False)}</span>')
    while is_fold(out):
        out.pop()
    return "\n".join(out)


def is_fold(out):
    return bool(out) and out[-1].startswith('<span class="fold"')


def fold_over(skipped):
    """A fold for the diff lines between two ranges, labelled by what they hold when that isn't unchanged code."""
    kinds = {HIDDEN.get(line[:1], "unchanged") for line in skipped if not line.startswith(("@@", "\\"))}
    if kinds <= {"unchanged"}:
        return FOLD
    return f'<span class="fold" data-hidden="{"changed" if len(kinds) > 1 else kinds.pop()}"></span>'


def gh_link(href, inner):
    return f'<a class="gh" href="{html.escape(href)}" target="_blank" rel="noopener">{inner}</a>'


def file_url(base, path):
    return f"{base}#diff-{hashlib.sha256(path.encode()).hexdigest()}"


def snip_start(diff, spec):
    """The first diff line of a SNIP spec and the path of its file, or (None, None) when it doesn't parse."""
    try:
        start = int(spec.replace(" ", "").split(",")[0].split("-")[0])
        return start, path_at(diff, header_of(diff, start)) if 1 <= start <= len(diff) else None
    except (ValueError, SnipError):
        return None, None


def link_body(body, diff, base, warnings):
    """Links file chips and snippet titles to the PR on GitHub, unless base is None for changes with no PR;
    returns the body and each file's first group."""
    files = diff_files(diff)
    paths = {f["path"] for f in files}
    groups = [(m.start(), m[2]) for m in GROUP.finditer(body)]

    first_group = {}
    for m in CHIP.finditer(body):
        gid = next((g for start, g in reversed(groups) if start < m.start()), None)
        if gid is None:
            continue
        chip = html.unescape(m[1])
        covered = [p for p in paths if p == chip or (chip.endswith("/") and p.startswith(chip))]
        if not covered:
            warnings.append(f"file chip {chip!r} is not in the diff")
        for p in covered:
            first_group.setdefault(p, gid)

    def link_chip(m):
        if base is None or html.unescape(m[1]) not in paths:
            return m[0]
        return f'<span class="file">{gh_link(file_url(base, html.unescape(m[1])), f"<b>{m[1]}</b>")}'

    def link_title(m):
        if not m[4]:
            if base is None:
                return m[1] + GH_LINK.sub(r"\1", m[2]) + m[3]
            if m[2].startswith("<a ") or html.unescape(m[2]) not in paths:
                return m[0]
            return m[1] + gh_link(file_url(base, html.unescape(m[2])), m[2]) + m[3]
        text = GH_LINK.sub(r"\1", m[2])
        start, path = snip_start(diff, m[4])
        if not path:
            return m[0]
        if path != html.unescape(text):
            warnings.append(f"snippet titled {html.unescape(text)!r} shows lines from {path!r}")
        if base is None:
            return m[1] + text + m[3]
        return m[1] + gh_link(file_url(base, path) + (line_anchor(diff, start) or ""), text) + m[3]

    body = CHIP.sub(link_chip, body)
    body = DIFF_TITLE.sub(link_title, body)

    missing = [f["path"] for f in files if f["path"] not in first_group]
    if missing:
        shown = ", ".join(missing[:10]) + (f" and {len(missing) - 10} more" if len(missing) > 10 else "")
        warnings.append(f"{len(missing)} changed files have no file chip in any group: {shown}")
    return body, first_group


def shown_lines(body, diff):
    """How many of each file's changed lines the page's snippets show, matched by content, so it holds for
    snippets SNIP expanded, hand-written ones and a page built earlier. Blank changed lines count as shown."""
    on_page = {}
    for m in SNIPPET.finditer(body):
        path = html.unescape(re.sub(r"<[^>]+>", "", m[1]))
        on_page.setdefault(path, Counter()).update(
            (SIGN[kind], html.unescape(text)) for kind, text in SNIPPET_LINE.findall(m[2]))
    shown = {}
    for f in diff_files(diff):
        seen, count = on_page.get(f["path"], Counter()), 0
        for line in diff[f["hunks"][0][0]:f["last"]] if f["hunks"] else []:
            key = (line[:1], line[1:])
            if key[0] in SIGN.values() and not key[1].strip():
                count += 1
            elif key[0] in SIGN.values() and seen[key] > 0:
                seen[key] -= 1
                count += 1
        shown[f["path"]] = count
    return shown


def not_fully_shown(body, diff, shown):
    """Files whose changed lines the snippets don't all show, leaving out lock files, generated code and files
    covered by a directory chip."""
    dirs = [html.unescape(c) for c in CHIP.findall(body) if c.endswith("/")]
    return [(f["path"], shown[f["path"]], f["adds"] + f["dels"]) for f in diff_files(diff)
            if shown[f["path"]] < f["adds"] + f["dels"] and not exempt(f, dirs)]


def exempt(f, dirs):
    """Lock files, generated code and files under a directory chip, which the snippets needn't show."""
    return f["generated"] or bool(LOCK_OR_GENERATED.search(f["path"])) or any(f["path"].startswith(d) for d in dirs)


def folded_at(body, pos):
    """True when the snippet holding position pos starts folded."""
    opens = list(SNIPPET_OPEN.finditer(body, 0, pos))
    return bool(opens) and "collapsed" in opens[-1][1].split()


def add_files_index(body, diff, first_group, shown, warnings):
    """Adds the rail's file list: each file linked to its group, with a pie of how much of it snippets show,
    and the share for the whole PR, split by tier when there is a supporting one."""
    supporting = {m[2] for m in GROUP.finditer(body) if m[1]}
    items, tiers = [], {"core": [0, 0], "supporting": [0, 0]}
    for f in diff_files(diff):
        tier = tiers["supporting" if first_group.get(f["path"]) in supporting else "core"]
        tier[0] += shown[f["path"]]
        tier[1] += f["adds"] + f["dels"]
        *folders, name = f["path"].split("/")
        label = "".join(f"{html.escape(d)}/<wbr>" for d in folders) + f"<b>{html.escape(name)}</b>"
        counts = (f'<span class="add">+{f["adds"]}</span>' if f["adds"] else "") + \
                 (f'<span class="del">−{f["dels"]}</span>' if f["dels"] else "")
        changed = f["adds"] + f["dels"]
        pie = ""
        if changed:
            note = f'{shown[f["path"]]} of {changed} changed lines shown in snippets'
            pie = (f'<span class="cov" role="img" style="--p: {round(100 * shown[f["path"]] / changed)}%" '
                   f'title="{note}" aria-label="{note}"></span>')
        inner = f'{pie}<span class="path">{label}</span>{counts}'
        gid = first_group.get(f["path"])
        items.append(f'<li><a href="#{gid}">{inner}</a></li>' if gid else f"<li><span>{inner}</span></li>")
    rail = body.find('<nav class="rail"')
    stat = body.find('<div class="stat">', rail) if rail >= 0 else -1
    if stat < 0:
        warnings.append('no <div class="stat"> in the rail; the file list was left out')
        return body
    on_page, total = (sum(t[i] for t in tiers.values()) for i in (0, 1))
    share, sentence = "", ""
    if total:
        share = f' <span class="share">· {round(100 * on_page / total)}% shown</span>'
        split = ", ".join(f"{round(100 * s / t)}% of {name}" for name, (s, t) in tiers.items() if t)
        sentence = (f'<p class="cov-total">Snippets show {on_page:,} of {total:,} changed lines'
                    f'{": " + split if supporting else ""}.</p>')
    return insert_before(body, stat, f'<details class="files-index"><summary>Files <span class="n">{len(items)}</span>'
                                     f'{share}</summary>{sentence}<ol>{"".join(items)}</ol></details>')


def number_groups(body, warnings):
    """Numbers the group headings in page order and the rail entries to match."""
    groups = list(GROUP.finditer(body))
    number = {m[2]: i for i, m in enumerate(groups, 1)}
    rail = [m[1] for m in RAIL_ITEM.finditer(body)]
    for gid in rail:
        if gid not in number:
            warnings.append(f"the rail links to #{gid}, which no group has")
    missing = [gid for gid in number if gid not in rail]
    if missing:
        warnings.append(f"groups missing from the rail: {', '.join(missing)}")
    listed = [gid for gid in rail if gid in number]
    if listed != sorted(listed, key=number.get):
        warnings.append("the rail lists the groups in a different order from the page")

    def renumber(m):
        if m[1] not in number:
            return m[0]
        return f'<li><a href="#{m[1]}"><span class="n">{number[m[1]]}</span>'

    parts = [body[:groups[0].start()] if groups else body]
    for i, m in enumerate(groups):
        end = groups[i + 1].start() if i + 1 < len(groups) else len(body)
        parts.append(GROUP_NUMBER.sub(rf"\g<1>{i + 1}\2", body[m.start():end], count=1))
    return RAIL_ITEM.sub(renumber, "".join(parts))


def insert_before(body, pos, block):
    """Inserts a generated block before pos, on its own line when pos starts one, so stripping the block
    and the whitespace after it restores the body."""
    indent = body[body.rfind("\n", 0, pos) + 1:pos]
    return body[:pos] + block + ("\n" + indent if not indent.strip() else "") + body[pos:]


def label_rail(body, gid, label):
    """Puts a tier label in the rail above the entry for group `gid`."""
    item = re.search(rf'<li><a href="#{re.escape(gid)}"><span class="n">', body)
    return insert_before(body, item.start(), f'<li class="tier">{label}</li>') if item else body


def check_figures(body, warnings):
    """Warns about a diagram placed after a snippet in its group: the shape comes before the lines."""
    starts = [(m.start(), m[2]) for m in GROUP.finditer(body)] + [(len(body), None)]
    for (start, gid), (end, _) in zip(starts, starts[1:]):
        section = body[start:end]
        figure, snippet = section.find('<figure class="figure"'), section.find('<div class="diff')
        if figure > snippet >= 0:
            warnings.append(f"group {gid!r} has its diagram after a snippet; put it after the purpose paragraph")


def mark_tiers(body, warnings):
    """Labels the review notes in the rail, and puts a 'Supporting changes' divider in the rail and the page
    before the first supporting group."""
    body = label_rail(body, "review", REVIEW_LABEL)
    groups = [(bool(m[1]), m[2], m.start()) for m in GROUP.finditer(body)]
    first = next((g for g in groups if g[0]), None)
    if not first:
        return body
    after_supporting = False
    for supporting, gid, _ in groups:
        if supporting:
            after_supporting = True
        elif after_supporting and gid != "review":
            warnings.append(f"core group {gid!r} comes after a supporting group; move it above them")
    _, gid, pos = first
    body = insert_before(body, pos, f'<p class="eyebrow tier">{TIER_LABEL}</p>')
    return label_rail(body, gid, TIER_LABEL)


def index(args):
    diff = read_lines(args.diff)
    for f in diff_files(diff):
        hunks = f["hunks"]
        span = f"hunk lines {hunks[0][0]}-{f['last']}" if hunks else "no hunks (binary, rename or mode change)"
        print(f"\n{f['path']}  ({span}){'  generated' if f['generated'] else ''}")
        for n, line in hunks:
            print(f"  {n:>6}  {line}")
            end_of_hunk = next((h for h, _ in hunks if h > n), f["last"] + 1)
            for m in range(n + 1, end_of_hunk):
                if LANDMARK.match(diff[m - 1]):
                    print(f"  {m:>6}      {diff[m - 1][1:].strip()[:90]}")
    return 0


def read_body(path):
    """The body file, or the page div of a page `build` wrote, with the parts `build` generates taken out."""
    text = path.read_text(encoding="utf-8")
    start = text.find('<div class="page">')
    if start > 0:
        end = text.find("<script>", start)
        text = text[start:end if end > 0 else None]
    for pattern, repl in GENERATED:
        text = pattern.sub(repl, text)
    return text.strip()


def active_content(body):
    """The first active content in the body, or None. The regex catches raw script tags and handlers whatever
    the parser makes of the markup around them; the parser reads URLs as a browser does, so a URL shown as
    escaped text is left alone."""
    match = ACTIVE.search(body)
    if match:
        return match.group(0)
    parser = ActiveContent()
    parser.feed(body)
    parser.close()
    return parser.found


def build(args):
    if bool(args.repo) != bool(args.pr):
        print("--repo and --pr go together; leave both out for changes that have no PR", file=sys.stderr)
        return 1
    template = TEMPLATE.read_text(encoding="utf-8")
    body = read_body(args.body)
    if not body.startswith('<div class="page">'):
        print('body must start with <div class="page">', file=sys.stderr)
        return 1
    active = active_content(body)
    if active:
        print(f"body must not carry active content ({active!r}); scripts and styles come from the template, "
              "and links use http, https, mailto or a #fragment", file=sys.stderr)
        return 1

    diff = read_lines(args.diff)
    warnings = []
    base = f"https://github.com/{args.repo}/pull/{args.pr}/files" if args.pr else None
    body, first_group = link_body(body, diff, base, warnings)
    body = number_groups(body, warnings)
    body = mark_tiers(body, warnings)
    check_figures(body, warnings)

    if SNIP.search(body):
        in_hunk = hunk_mask(diff)
        errors, expanded = [], 0

        def expand(match):
            nonlocal expanded
            notes = []
            try:
                out = render(diff, in_hunk, match.group(1), notes)
            except SnipError as e:
                errors.append(f"{match.group(0)}: {e}")
                return match.group(0)
            for note in notes:
                print(f"note: {match.group(0)}: {note}", file=sys.stderr)
            expanded += 1
            lines = sum(1 for line in out.split("\n") if not line.startswith('<span class="fold"'))
            if lines > LONG_SNIPPET and not folded_at(match.string, match.start()):
                print(f"warning: {match.group(0)} is {lines} lines; trim it to the lines that carry the point, "
                      "or fold it if it is there for completeness", file=sys.stderr)
            return out

        body = SNIP.sub(expand, body)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print(f"expanded {expanded} SNIP markers")

    if FLOW.search(body):
        errors, count = [], 0

        def draw(match):
            nonlocal count
            try:
                svg = flow.render(match.group(1), count)
            except flow.FlowError as e:
                errors.append(f"FLOW #{count + 1}: {e}")
                return match.group(0)
            count += 1
            width = flow.width(svg)
            if width > flow.MAX_WIDTH:
                warnings.append(f"FLOW #{count} is {width} px wide, over the page's {flow.MAX_WIDTH}, and shrinks to fit; "
                                "split it, shorten names or drop nodes")
            return svg

        body = FLOW.sub(draw, body)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print(f"drew {count} FLOW diagrams")

    shown = shown_lines(body, diff)
    for path, n, total in not_fully_shown(body, diff, shown):
        warnings.append(f"{path!r} shows {n} of its {total} changed lines; show the rest in the group it belongs to, "
                        "folded if it is minor")
    body = add_files_index(body, diff, first_group, shown, warnings)
    dirs = [html.unescape(c) for c in CHIP.findall(body) if c.endswith("/")]
    changed = {f["path"]: f["adds"] + f["dels"] for f in diff_files(diff) if not exempt(f, dirs)}
    total, on_page = sum(changed.values()), sum(shown.values())
    partial = sum(1 for path, n in changed.items() if shown[path] < n)
    if total:
        print(f"snippets show {on_page} of {total} changed lines ({round(100 * on_page / total)}%); "
              f"{partial} of {len(changed)} files not fully shown, leaving out lock files and generated code")

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    start = template.index('<div class="page">')
    end = template.index("<script>", start)
    name = html.escape(f"PR {args.pr}" if args.pr else args.name or "Local changes")
    page = (template[:start] + body + "\n\n" + template[end:]).replace(
        "<title>PR 0000 Review Guide</title>", f"<title>{name} Review Guide</title>", 1)
    if args.standalone:
        page = DOCUMENT_HEAD + page

    args.out.write_text(page, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="list files and hunk line numbers in a diff")
    p_index.add_argument("diff", type=Path)
    p_index.set_defaults(func=index)

    p_build = sub.add_parser("build", help="expand SNIP markers and splice the body into the template")
    p_build.add_argument("--repo", help="owner/repo, for the links to the PR on GitHub")
    p_build.add_argument("--pr", help="PR number, for <title> and the links; leave out with --repo for local changes")
    p_build.add_argument("--name", help="what <title> names when there is no PR, such as the branch")
    p_build.add_argument("--diff", type=Path, required=True, help="the diff that SNIP ranges and links point into")
    p_build.add_argument("--standalone", action="store_true",
                         help="prepend a doctype and charset, for agents without an Artifact tool")
    p_build.add_argument("body", type=Path, help='file holding <div class="page"> ... </div>, or a page build wrote')
    p_build.add_argument("out", type=Path, help="page to write")
    p_build.set_defaults(func=build)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
