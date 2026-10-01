"""The chip: qubits on a grid and the couplers (edges) between them.

Pure Python, no pygame, so it is unit tested directly.

Two layouts share the same square node grid, which keeps the stick mapping to
four directions:

- "square": every horizontal and vertical neighbour is coupled (degree <= 4,
  Google-style).
- "brick": all horizontal couplers, but only every other vertical one,
  staggered row by row like a brick wall. That is exactly hexagonal
  connectivity (degree <= 3, the same graph as IBM's heavy-hex without the
  extra coupler qubits), drawn without any diagonal edges.
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


def edge(a: Node, b: Node) -> Edge:
    return frozenset((a, b))


class Lattice:
    def __init__(self, kind: str, rows: int, cols: int):
        if kind not in ("square", "brick"):
            raise ValueError(f"unknown lattice kind: {kind!r}")
        self.kind = kind
        self.rows = rows
        self.cols = cols
        self.nodes: list[Node] = [(r, c) for r in range(rows) for c in range(cols)]
        self.edges: set[Edge] = set()
        for r in range(rows):
            for c in range(cols):
                if c + 1 < cols:
                    self.edges.add(edge((r, c), (r, c + 1)))
                if r + 1 < rows and (kind == "square" or (r + c) % 2 == 0):
                    self.edges.add(edge((r, c), (r + 1, c)))
        self._dist: dict[Node, dict[Node, int]] = {}

    def has_edge(self, a: Node, b: Node) -> bool:
        return edge(a, b) in self.edges

    def neighbor(self, node: Node, direction: str) -> Node | None:
        """The node coupled to `node` in that direction, or None if no coupler."""
        dr, dc = DIRECTIONS[direction]
        other = (node[0] + dr, node[1] + dc)
        return other if self.has_edge(node, other) else None

    def neighbors(self, node: Node) -> list[Node]:
        return [n for d in DIRECTIONS if (n := self.neighbor(node, d)) is not None]

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
