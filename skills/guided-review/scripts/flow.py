"""Render a small box-and-arrow diagram as inline SVG styled by the template's theme tokens.

The source is one edge or chain per line:

    HTTPUploader -> ingester -> loggingSubmitter*
    loggingSubmitter -> dryRunSubmitter : dry-run
    loggingSubmitter -> real uploader : live
    Stop -> Start : restart

`A -> B : label` labels that edge (on a chain, the last edge). A trailing `*` marks a node the PR adds; once
is enough, since a node is the same box wherever its name appears. An edge from a node to itself is refused.
Lines starting with `#` are comments. Nodes are laid out left to right in layers by longest path; an
edge that points back to an earlier layer (a loop) is drawn as a curve underneath. Which edge of a cycle
becomes the loop doesn't depend on line order: the walk starts from nodes nothing points to, then from
nodes only labeled edges point to, so the unlabeled main path runs left to right. Other nodes keep line order.
"""
import html

CHAR_W = 7.4
BOX_H = 34
ROW_GAP = 20
MIN_GAP = 56
PAD = 16
LOOP_DROP = 34
MAX_WIDTH = 1000


class FlowError(Exception):
    pass


def parse(src):
    nodes, new, edges = [], set(), []

    def node(name):
        name = name.strip()
        if name.endswith("*"):
            name = name[:-1].strip()
            new.add(name)
        if not name:
            raise FlowError("empty node name")
        if name not in nodes:
            nodes.append(name)
        return name

    for raw in src.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        label = ""
        if " : " in line:
            line, label = line.split(" : ", 1)
        parts = line.split("->")
        if len(parts) < 2:
            raise FlowError(f"no '->' in line {raw.strip()!r}")
        names = [node(p) for p in parts]
        for i, (a, b) in enumerate(zip(names, names[1:])):
            if a == b:
                raise FlowError(f"{a!r} points to itself in line {raw.strip()!r}")
            edges.append((a, b, label.strip() if i == len(names) - 2 else ""))
    if not edges:
        raise FlowError("diagram has no edges")
    return nodes, new, edges


def layout(nodes, edges):
    succ = {n: [] for n in nodes}
    for a, b, _ in edges:
        succ[a].append(b)

    back, state = set(), {}

    def visit(n):
        state[n] = "open"
        for m in succ[n]:
            if state.get(m) == "open":
                back.add((n, m))
            elif m not in state:
                visit(m)
        state[n] = "done"

    incoming = {n: set() for n in nodes}
    for _, b, label in edges:
        incoming[b].add(bool(label))

    def start_rank(n):
        if not incoming[n]:
            return 0
        return 1 if incoming[n] == {True} else 2

    for n in sorted(nodes, key=start_rank):
        if n not in state:
            visit(n)

    layer = {n: 0 for n in nodes}
    for _ in nodes:
        changed = False
        for a, b, _ in edges:
            if (a, b) not in back and layer[b] < layer[a] + 1:
                layer[b] = layer[a] + 1
                changed = True
        if not changed:
            break
    return layer, back


def render(src, idx):
    nodes, new, edges = parse(src)
    layer, back = layout(nodes, edges)

    width = {n: max(84, round(len(n) * CHAR_W + 28)) for n in nodes}
    columns = {}
    for n in nodes:
        columns.setdefault(layer[n], []).append(n)

    gaps = {}
    for a, b, label in edges:
        if (a, b) in back:
            continue
        span = max(1, layer[b] - layer[a])
        need = (len(label) * 6.6 + 48) / span if label else 0
        for g in range(layer[a], layer[b]):
            gaps[g] = max(gaps.get(g, MIN_GAP), need, MIN_GAP)

    col_x, x = {}, PAD
    for c in sorted(columns):
        col_x[c] = x
        x += max(width[n] for n in columns[c]) + gaps.get(c, MIN_GAP)
    total_w = x - gaps.get(max(columns), MIN_GAP) + PAD

    tallest = max(len(v) for v in columns.values())
    body_h = tallest * BOX_H + (tallest - 1) * ROW_GAP
    pos = {}
    for c, members in columns.items():
        col_h = len(members) * BOX_H + (len(members) - 1) * ROW_GAP
        y0 = PAD + (body_h - col_h) / 2
        col_w = max(width[n] for n in members)
        for i, n in enumerate(members):
            pos[n] = (col_x[c] + (col_w - width[n]) / 2, y0 + i * (BOX_H + ROW_GAP))
    total_h = PAD * 2 + body_h + (LOOP_DROP + 14 if back else 0)

    marker = f"flow-arrow-{idx}"
    out = [f'<svg class="flow" viewBox="0 0 {total_w:.0f} {total_h:.0f}" width="{total_w:.0f}" '
           f'role="img" aria-label="{html.escape(describe(edges))}">',
           f'<defs><marker id="{marker}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"/></marker></defs>']

    labels = []
    for a, b, label in edges:
        ax, ay = pos[a]
        bx, by = pos[b]
        if (a, b) in back:
            sx, sy = ax + width[a] / 2, ay + BOX_H
            tx, ty = bx + width[b] / 2, by + BOX_H
            low = PAD + body_h + LOOP_DROP
            d = f"M{sx:.1f},{sy:.1f} C{sx:.1f},{low:.1f} {tx:.1f},{low:.1f} {tx:.1f},{ty + 2:.1f}"
            mid = ((sx + tx) / 2, low - 4)
        else:
            sx, sy = ax + width[a], ay + BOX_H / 2
            tx, ty = bx - 2, by + BOX_H / 2
            dx = (tx - sx) / 2
            d = f"M{sx:.1f},{sy:.1f} C{sx + dx:.1f},{sy:.1f} {tx - dx:.1f},{ty:.1f} {tx:.1f},{ty:.1f}"
            mid = ((sx + tx) / 2, (sy + ty) / 2)
        out.append(f'<path class="edge" d="{d}" marker-end="url(#{marker})"/>')
        if label:
            labels.append((mid, label))

    for n in nodes:
        x0, y0 = pos[n]
        cls = "node new" if n in new else "node"
        out.append(f'<g class="{cls}"><rect x="{x0:.1f}" y="{y0:.1f}" width="{width[n]}" height="{BOX_H}" rx="6"/>'
                   f'<text x="{x0 + width[n] / 2:.1f}" y="{y0 + BOX_H / 2 + 4:.1f}">{html.escape(n)}</text></g>')

    for (mx, my), label in labels:
        w = len(label) * 6.6 + 10
        out.append(f'<g class="edge-label"><rect x="{mx - w / 2:.1f}" y="{my - 9:.1f}" width="{w:.1f}" height="16" rx="3"/>'
                   f'<text x="{mx:.1f}" y="{my + 3:.1f}">{html.escape(label)}</text></g>')

    out.append("</svg>")
    return "".join(out)


def width(svg):
    """The drawn width of an SVG that render returned."""
    return int(svg.split('width="', 1)[1].split('"', 1)[0])


def describe(edges):
    return "Diagram: " + "; ".join(f"{a} to {b}" + (f" ({label})" if label else "") for a, b, label in edges)
