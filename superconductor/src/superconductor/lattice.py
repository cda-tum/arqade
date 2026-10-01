"""The chip: qubits on a grid and the couplers (edges) between them.

Pure Python, no pygame, so it is unit tested directly.

Every layout puts its qubits on integer (row, col) grid points and only ever
couples grid neighbours, so the stick always maps to four directions. Some
layouts draw groups of qubits further apart (`positions`), which only changes
the picture, not the graph.

- "square": 5x5, every horizontal and vertical neighbour coupled (degree <= 4,
  Google-style).
- "brick": 5x5 with all horizontal couplers but only every other vertical one,
  staggered like a brick wall. That is exactly hexagonal connectivity (degree
  <= 3, the graph behind IBM's heavy-hex), drawn without diagonals.
- "bottleneck": two 3x4 blocks, one above the other, joined only through the
  middle two columns.
- "distributed": four 3x3 modules in a 2x2 arrangement. Each module is linked
  to each neighbouring module by a single coupler between the middle qubits
  of their facing sides, like a modular / networked quantum computer.
"""

from __future__ import annotations

from collections import deque

Node = tuple[int, int]  # (row, col)
Edge = frozenset  # frozenset({node_a, node_b})

DIRECTIONS: dict[str, tuple[int, int]] = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}
LAYOUTS = ("square", "brick", "bottleneck", "distributed")
MODULE_GAP = 0.6  # extra drawing distance between blocks / modules


def edge(a: Node, b: Node) -> Edge:
    return frozenset((a, b))


def _grid(rows: int, cols: int) -> list[Node]:
    return [(r, c) for r in range(rows) for c in range(cols)]


def _neighbour_pairs(nodes: list[Node]):
    """Every pair of grid neighbours (right and down) among `nodes`."""
    present = set(nodes)
    for r, c in nodes:
        for other in ((r, c + 1), (r + 1, c)):
            if other in present:
                yield (r, c), other


class Lattice:
    def __init__(self, kind: str, rows: int = 5, cols: int = 5):
        """`rows`/`cols` size the square and brick layouts; the others are fixed."""
        if kind not in LAYOUTS:
            raise ValueError(f"unknown lattice kind: {kind!r}")
        self.kind = kind
        self.edges: set[Edge] = set()
        self.bridges: set[Edge] = set()  # couplers between blocks / modules
        if kind in ("square", "brick"):
            self.nodes = _grid(rows, cols)
            for a, b in _neighbour_pairs(self.nodes):
                vertical = a[1] == b[1]
                if kind == "square" or not vertical or (a[0] + a[1]) % 2 == 0:
                    self.edges.add(edge(a, b))
            self.positions = {n: (float(n[0]), float(n[1])) for n in self.nodes}
        elif kind == "bottleneck":
            self.nodes = _grid(6, 4)
            for a, b in _neighbour_pairs(self.nodes):
                crossing = a[0] // 3 != b[0] // 3
                if not crossing:
                    self.edges.add(edge(a, b))
                elif a[1] in (1, 2):
                    self.edges.add(edge(a, b))
                    self.bridges.add(edge(a, b))
            self.positions = {n: (n[0] + MODULE_GAP * (n[0] >= 3), float(n[1])) for n in self.nodes}
        else:  # distributed
            self.nodes = _grid(6, 6)
            for a, b in _neighbour_pairs(self.nodes):
                if (a[0] // 3, a[1] // 3) == (b[0] // 3, b[1] // 3):
                    self.edges.add(edge(a, b))
            for a, b in (((1, 2), (1, 3)), ((4, 2), (4, 3)), ((2, 1), (3, 1)), ((2, 4), (3, 4))):
                self.edges.add(edge(a, b))
                self.bridges.add(edge(a, b))
            self.positions = {n: (n[0] + MODULE_GAP * (n[0] >= 3), n[1] + MODULE_GAP * (n[1] >= 3))
                              for n in self.nodes}
        self.rows = max(r for r, _ in self.nodes) + 1
        self.cols = max(c for _, c in self.nodes) + 1
        self._neighbors: dict[Node, list[Node]] = {}
        self._dist: dict[Node, dict[Node, int]] = {}

    def has_edge(self, a: Node, b: Node) -> bool:
        return edge(a, b) in self.edges

    def neighbor(self, node: Node, direction: str) -> Node | None:
        """The node coupled to `node` in that direction, or None if no coupler."""
        dr, dc = DIRECTIONS[direction]
        other = (node[0] + dr, node[1] + dc)
        return other if self.has_edge(node, other) else None

    def neighbors(self, node: Node) -> list[Node]:
        if node not in self._neighbors:
            self._neighbors[node] = [n for d in DIRECTIONS if (n := self.neighbor(node, d)) is not None]
        return self._neighbors[node]

    def extent(self) -> tuple[float, float, float, float]:
        """(min_y, min_x, max_y, max_x) of the drawing positions."""
        ys = [y for y, _ in self.positions.values()]
        xs = [x for _, x in self.positions.values()]
        return min(ys), min(xs), max(ys), max(xs)

    def distance(self, a: Node, b: Node) -> int:
        """Hops between a and b on the empty chip (BFS, cached per source)."""
        if a not in self._dist:
            dist = {a: 0}
            queue = deque([a])
            while queue:
                n = queue.popleft()
                for m in self.neighbors(n):
                    if m not in dist:
                        dist[m] = dist[n] + 1
                        queue.append(m)
            self._dist[a] = dist
        return self._dist[a][b]
