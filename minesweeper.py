"""Campo minado que se joga sozinho: cada execução faz uma jogada e redesenha o SVG."""
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "minesweeper.json"
SVG_FILE = ROOT / "minesweeper.svg"
README = ROOT / "README.md"

W, H, N_MINES = 12, 9, 14
CELL, PAD, HEADER, FOOTER = 30, 16, 44, 34

NUMBER_COLORS = {
    1: "#58a6ff", 2: "#3fb950", 3: "#f85149", 4: "#bc8cff",
    5: "#d29922", 6: "#39c5cf", 7: "#c9d1d9", 8: "#8b949e",
}


def neighbors(r, c):
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if (dr or dc) and 0 <= r + dr < H and 0 <= c + dc < W:
                yield r + dr, c + dc


def new_game(wins=0, losses=0, version=0):
    return {
        "mines": None,
        "revealed": [[False] * W for _ in range(H)],
        "flags": [[False] * W for _ in range(H)],
        "status": "playing",
        "exploded": None,
        "wins": wins,
        "losses": losses,
        "version": version,
    }


def load():
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return new_game()
    if state["mines"] is not None:
        state["mines"] = {tuple(m) for m in state["mines"]}
    if state["exploded"] is not None:
        state["exploded"] = tuple(state["exploded"])
    return state


def save(state):
    data = dict(state)
    if data["mines"] is not None:
        data["mines"] = sorted(list(m) for m in data["mines"])
    if data["exploded"] is not None:
        data["exploded"] = list(data["exploded"])
    STATE_FILE.write_text(json.dumps(data), encoding="utf-8")


def number(state, r, c):
    return sum(nb in state["mines"] for nb in neighbors(r, c))


def place_mines(state, start):
    banned = {start, *neighbors(*start)}
    cells = [(r, c) for r in range(H) for c in range(W) if (r, c) not in banned]
    state["mines"] = set(random.sample(cells, N_MINES))


def reveal(state, r, c):
    stack = [(r, c)]
    while stack:
        r, c = stack.pop()
        if state["revealed"][r][c] or state["flags"][r][c]:
            continue
        state["revealed"][r][c] = True
        if (r, c) in state["mines"]:
            state["status"] = "lost"
            state["exploded"] = (r, c)
            state["losses"] += 1
            return
        if number(state, r, c) == 0:
            stack.extend(neighbors(r, c))


def deduce(state):
    """Regras simples: número já cumprido => resto é seguro; faltam = desconhecidos => todos minas."""
    new_flags, safe = set(), set()
    for r in range(H):
        for c in range(W):
            if not state["revealed"][r][c]:
                continue
            n = number(state, r, c)
            if n == 0:
                continue
            unknown = [
                nb for nb in neighbors(r, c)
                if not state["revealed"][nb[0]][nb[1]] and not state["flags"][nb[0]][nb[1]]
            ]
            if not unknown:
                continue
            flagged = sum(state["flags"][nr][nc] for nr, nc in neighbors(r, c))
            remaining = n - flagged
            if remaining == 0:
                safe.update(unknown)
            elif remaining == len(unknown):
                new_flags.update(unknown)
    return new_flags, safe


def guess(state):
    unknown = [
        (r, c) for r in range(H) for c in range(W)
        if not state["revealed"][r][c] and not state["flags"][r][c]
    ]
    flagged_total = sum(sum(row) for row in state["flags"])
    prob = {}
    for r in range(H):
        for c in range(W):
            if not state["revealed"][r][c]:
                continue
            n = number(state, r, c)
            cells = [nb for nb in neighbors(r, c) if nb in set(unknown)]
            if n == 0 or not cells:
                continue
            flagged = sum(state["flags"][nr][nc] for nr, nc in neighbors(r, c))
            p = max(n - flagged, 0) / len(cells)
            for nb in cells:
                prob[nb] = max(prob.get(nb, 0), p)
    others = [cell for cell in unknown if cell not in prob]
    if others:
        p_other = (N_MINES - flagged_total) / len(unknown)
        for cell in others:
            prob[cell] = p_other
    best = min(prob.values())
    return random.choice([cell for cell, p in prob.items() if p == best])


def check_win(state):
    if state["status"] != "playing":
        return
    revealed = sum(sum(row) for row in state["revealed"])
    if revealed == W * H - N_MINES:
        state["status"] = "won"
        state["wins"] += 1
        for r, c in state["mines"]:
            state["flags"][r][c] = True


def play_turn(state):
    state["version"] += 1
    if state["status"] != "playing":
        fresh = new_game(state["wins"], state["losses"], state["version"])
        state.clear()
        state.update(fresh)
        return
    if state["mines"] is None:
        start = (H // 2, W // 2)
        place_mines(state, start)
        reveal(state, *start)
        return
    while True:
        new_flags, safe = deduce(state)
        for r, c in new_flags:
            state["flags"][r][c] = True
        if safe:
            for r, c in safe:
                reveal(state, r, c)
            break
        if not new_flags:
            reveal(state, *guess(state))
            break
    check_win(state)


def render(state):
    width = PAD * 2 + W * CELL
    height = PAD + HEADER + H * CELL + FOOTER + PAD
    top = PAD + HEADER
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="Segoe UI, Arial, sans-serif">',
        f'<rect width="{width}" height="{height}" rx="14" fill="#0d1117" stroke="#30363d"/>',
        f'<text x="{PAD}" y="{PAD + 22}" font-size="17" font-weight="700" fill="#f08228">Minesweeper</text>',
        f'<text x="{width - PAD}" y="{PAD + 22}" font-size="13" text-anchor="end" fill="#8b949e">wins {state["wins"]}  ·  losses {state["losses"]}</text>',
    ]
    for r in range(H):
        for c in range(W):
            x, y = PAD + c * CELL, top + r * CELL
            cx, cy = x + CELL / 2, y + CELL / 2
            revealed = state["revealed"][r][c]
            is_mine = state["mines"] is not None and (r, c) in state["mines"]
            show_mine = is_mine and state["status"] == "lost"
            if revealed or show_mine:
                fill = "#da3633" if state["exploded"] == (r, c) else "#161b22"
                out.append(f'<rect x="{x + 1}" y="{y + 1}" width="{CELL - 2}" height="{CELL - 2}" rx="4" fill="{fill}"/>')
            else:
                out.append(f'<rect x="{x + 1}" y="{y + 1}" width="{CELL - 2}" height="{CELL - 2}" rx="4" fill="#30363d" stroke="#484f58"/>')
            if show_mine and not state["flags"][r][c]:
                out.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="#e6edf3"/>')
            elif state["flags"][r][c]:
                out.append(f'<line x1="{cx - 3}" y1="{cy - 8}" x2="{cx - 3}" y2="{cy + 8}" stroke="#c9d1d9" stroke-width="2"/>')
                out.append(f'<polygon points="{cx - 3},{cy - 8} {cx + 7},{cy - 4} {cx - 3},{cy}" fill="#f08228"/>')
            elif revealed and not is_mine:
                n = number(state, r, c)
                if n:
                    out.append(f'<text x="{cx}" y="{cy + 6}" font-size="17" font-weight="700" text-anchor="middle" fill="{NUMBER_COLORS[n]}">{n}</text>')
    status = {"playing": "playing...", "won": "won! a new game starts soon", "lost": "boom! a new game starts soon"}[state["status"]]
    out.append(f'<text x="{PAD}" y="{height - PAD - 6}" font-size="13" fill="#8b949e">{status}</text>')
    out.append(f'<text x="{width - PAD}" y="{height - PAD - 6}" font-size="12" text-anchor="end" fill="#6e7681">plays itself every hour</text>')
    out.append("</svg>")
    SVG_FILE.write_text("\n".join(out), encoding="utf-8")


def bump_readme(version):
    if not README.exists():
        return
    text = README.read_text(encoding="utf-8")
    new = re.sub(r"minesweeper\.svg\?v=\d+", f"minesweeper.svg?v={version}", text)
    if new != text:
        README.write_text(new, encoding="utf-8")


def main():
    state = load()
    play_turn(state)
    save(state)
    render(state)
    bump_readme(state["version"])


if __name__ == "__main__":
    main()
