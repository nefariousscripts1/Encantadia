"""Graph data, A* path-finding, and Dijkstra verification logic for the Argentina map."""

from __future__ import annotations

import heapq
import math
from typing import Any


WIDTH = 1409
HEIGHT = 1117
# This becomes approximately 12 CSS pixels when the Canvas is displayed at its
# intended maximum width of 700 CSS pixels.
NODE_RADIUS = 24

# These drawing coordinates were calibrated against argentina_map.png after it
# is drawn at its native 1409 x 1117 size. One map pixel therefore equals one
# graph coordinate, with no crop, offset, or aspect-ratio conversion.
VERTICES: dict[str, tuple[float, float]] = {
    "A": (237.2, 60.4),
    "B": (189.0, 250.0),
    "C": (147.0, 338.0),
    "D": (199.0, 694.0),
    "E": (223.0, 892.0),
    "F": (270.0, 1061.0),
    "G": (638.0, 155.0),
    "H": (600.0, 350.0),
    "I": (403.0, 300.0),
    "J": (409.0, 696.0),
    "K": (604.0, 696.0),
    "L": (606.0, 892.0),
    "M": (608.0, 1061.0),
    "N": (1071.0, 60.4),
    "O": (1016.6, 255.7),
    "P": (973.2, 440.2),
    "Q": (794.0, 399.0),
    "R": (789.0, 696.0),
    "S": (970.0, 696.0),
    "T": (972.0, 892.0),
    "U": (972.0, 1063.0),
    "V": (1164.0, 77.4),
    "W": (1210.0, 300.0),
    "X": (1304.0, 523.6),
    "Y": (1339.0, 703.0),
    "Z": (1367.0, 877.2),
    "Z1": (1284.0, 1063.0),
}

LABELS = list(VERTICES)
INDEX = {label: position for position, label in enumerate(LABELS)}

# Fixed weights copied from the original graph.
EDGE_DEFINITIONS: list[tuple[str, str, float]] = [
    ("A", "B", 88.6),
    ("A", "G", 195.0),
    ("B", "C", 53.7),
    ("B", "I", 106.2),
    ("C", "D", 166.8),
    ("D", "E", 95.7),
    ("D", "J", 96.6),
    ("E", "F", 79.5),
    ("E", "L", 170.3),
    ("F", "M", 153.6),
    ("G", "H", 90.9),
    ("G", "O", 183.5),
    ("H", "I", 92.7),
    ("H", "K", 169.5),
    ("H", "Q", 93.1),
    ("I", "J", 185.3),
    ("J", "K", 90.3),
    ("K", "L", 93.3),
    ("K", "R", 90.7),
    ("L", "M", 78.4),
    ("L", "T", 175.8),
    ("M", "U", 175.6),
    ("N", "O", 93.6),
    ("N", "V", 43.2),
    ("O", "P", 87.4),
    ("O", "W", 92.3),
    ("P", "Q", 89.9),
    ("P", "S", 124.0),
    ("P", "X", 164.1),
    ("Q", "R", 143.0),
    ("R", "S", 85.0),
    ("S", "T", 90.0),
    ("S", "Y", 169.0),
    ("T", "U", 83.8),
    ("T", "Z", 177.0),
    ("U", "Z1", 180.0),
    ("V", "W", 101.4),
    ("W", "X", 120.4),
    ("X", "Y", 83.5),
    ("Y", "Z", 84.4),
]

EDGES = [(edge_start, edge_end) for edge_start, edge_end, _ in EDGE_DEFINITIONS]

LOGICAL_COORDINATES: dict[str, tuple[float, float]] = {
    "A": (112, 27.2), "B": (89.5, 112.9), "C": (70.3, 163.1),
    "D": (95.9, 327.9), "E": (112.4, 422.2), "F": (129.1, 499.9),
    "G": (302.1, 70.6), "H": (282.8, 159.4), "I": (191.9, 141.2),
    "J": (192.5, 326.5), "K": (282.8, 328.9), "L": (282.7, 422.2),
    "M": (282.7, 500.6), "N": (505.3, 29.4), "O": (479.0, 119.2),
    "P": (460.1, 204.5), "Q": (372.5, 184.5), "R": (373.5, 327.5),
    "S": (458.5, 328.5), "T": (458.5, 418.5), "U": (458.3, 502.3),
    "V": (547.5, 38.5), "W": (569.5, 137.5), "X": (618.5, 247.5),
    "Y": (627.5, 330.5), "Z": (635.5, 414.5), "Z1": (638.3, 500.1),
}

# Scaling by the smallest edge ratio guarantees the Euclidean heuristic is admissible.
HEURISTIC_SCALE = min(
    weight / math.dist(LOGICAL_COORDINATES[edge_start], LOGICAL_COORDINATES[edge_end])
    for edge_start, edge_end, weight in EDGE_DEFINITIONS
)


def euclidean_distance(first: str, second: str) -> float:
    """Return the logical Euclidean distance between two nodes."""
    return math.dist(LOGICAL_COORDINATES[first], LOGICAL_COORDINATES[second])


def heuristic(node: str, goal: str) -> float:
    """Return an admissible, normalized Euclidean estimate h(n)."""
    return euclidean_distance(node, goal) * HEURISTIC_SCALE


EDGE_DISTANCES: dict[tuple[str, str], float] = {}
ADJACENCY = [[0.0] * len(LABELS) for _ in LABELS]

for edge_start, edge_end, distance in EDGE_DEFINITIONS:
    start_idx = INDEX[edge_start]
    end_idx = INDEX[edge_end]
    ADJACENCY[start_idx][end_idx] = distance
    ADJACENCY[end_idx][start_idx] = distance
    EDGE_DISTANCES[(edge_start, edge_end)] = distance
    EDGE_DISTANCES[(edge_end, edge_start)] = distance


def a_star(start: str, goal: str) -> dict[str, Any]:
    """Execute A* search using original graph weights and admissible heuristic.

    Uses:
    - Min-heap priority queue
    - g_score tracking actual accumulated cost
    - came_from map for shortest-path reconstruction
    - Admissible heuristic f(n) = g(n) + h(n)

    Returns:
    - path: list of node labels from start to goal
    - edge_weights: list of weights for each traversed edge
    - total_cost: total accumulated path weight
    - start_cost: initial {g, h, f} values for start node
    - explored: step-by-step neighbor exploration records
    - path_edges: edge list with from, to, and weight
    """
    if start not in VERTICES:
        raise ValueError(f"Unknown start node: {start}")
    if goal not in VERTICES:
        raise ValueError(f"Unknown goal node: {goal}")

    start_h = heuristic(start, goal)
    start_cost = {"g": 0.0, "h": round(start_h, 1), "f": round(start_h, 1)}

    if start == goal:
        return {
            "path": [start],
            "edge_weights": [],
            "total_cost": 0.0,
            "start_cost": start_cost,
            "explored": [],
            "path_edges": [],
        }

    # Priority queue holds tuples of (f_cost, sequence_id, node_label)
    counter = 0
    priority_queue: list[tuple[float, int, str]] = [(start_h, counter, start)]
    g_costs = {label: math.inf for label in LABELS}
    g_costs[start] = 0.0
    came_from: dict[str, str] = {}
    explored: list[dict[str, Any]] = []
    closed: set[str] = set()

    while priority_queue:
        _, _, current = heapq.heappop(priority_queue)

        if current == goal:
            break

        if current in closed:
            continue
        closed.add(current)

        for neighbor_index, edge_cost in enumerate(ADJACENCY[INDEX[current]]):
            if edge_cost == 0.0:
                continue

            neighbor = LABELS[neighbor_index]
            if neighbor in closed:
                continue

            tentative_g = g_costs[current] + edge_cost
            if tentative_g < g_costs[neighbor]:
                g_costs[neighbor] = tentative_g
                came_from[neighbor] = current
                h_cost = heuristic(neighbor, goal)
                f_cost = tentative_g + h_cost
                counter += 1
                heapq.heappush(priority_queue, (f_cost, counter, neighbor))
                explored.append(
                    {
                        "from": current,
                        "to": neighbor,
                        "weight": edge_cost,
                        "g": round(tentative_g, 1),
                        "h": round(h_cost, 1),
                        "f": round(f_cost, 1),
                    }
                )

    if goal not in came_from:
        return {
            "path": [],
            "edge_weights": [],
            "total_cost": None,
            "start_cost": start_cost,
            "explored": explored,
            "path_edges": [],
        }

    path = [goal]
    while path[-1] in came_from:
        path.append(came_from[path[-1]])
    path.reverse()

    edge_weights = [
        EDGE_DISTANCES[(path[i], path[i + 1])] for i in range(len(path) - 1)
    ]
    path_edges = [
        {
            "from": path[i],
            "to": path[i + 1],
            "weight": edge_weights[i],
        }
        for i in range(len(path) - 1)
    ]

    return {
        "path": path,
        "edge_weights": edge_weights,
        "total_cost": round(g_costs[goal], 1),
        "start_cost": start_cost,
        "explored": explored,
        "path_edges": path_edges,
    }


# Alias for backward compatibility
astar = a_star


def dijkstra(start: str, goal: str) -> dict[str, Any]:
    """Standard Dijkstra's algorithm for shortest-path verification."""
    if start not in VERTICES:
        raise ValueError(f"Unknown start node: {start}")
    if goal not in VERTICES:
        raise ValueError(f"Unknown goal node: {goal}")

    if start == goal:
        return {"path": [start], "total_cost": 0.0}

    counter = 0
    pq: list[tuple[float, int, str]] = [(0.0, counter, start)]
    distances = {label: math.inf for label in LABELS}
    distances[start] = 0.0
    came_from: dict[str, str] = {}
    visited: set[str] = set()

    while pq:
        dist, _, current = heapq.heappop(pq)
        if current == goal:
            break
        if current in visited:
            continue
        visited.add(current)

        for neighbor_index, edge_cost in enumerate(ADJACENCY[INDEX[current]]):
            if edge_cost == 0.0:
                continue
            neighbor = LABELS[neighbor_index]
            if neighbor in visited:
                continue
            new_dist = dist + edge_cost
            if new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                came_from[neighbor] = current
                counter += 1
                heapq.heappush(pq, (new_dist, counter, neighbor))

    if goal not in came_from:
        return {"path": [], "total_cost": None}

    path = [goal]
    while path[-1] in came_from:
        path.append(came_from[path[-1]])
    path.reverse()

    return {
        "path": path,
        "total_cost": round(distances[goal], 1),
    }


def graph_payload() -> dict[str, Any]:
    """Return all data needed to draw the graph in a web browser."""
    nodes = [
        {"id": label, "x": coordinates[0], "y": coordinates[1]}
        for label, coordinates in VERTICES.items()
    ]
    edges = [
        {
            "from": edge_start,
            "to": edge_end,
            "weight": EDGE_DISTANCES[(edge_start, edge_end)],
        }
        for edge_start, edge_end in EDGES
    ]

    return {
        "nodes": nodes,
        "coordinates": {
            label: [coordinates[0], coordinates[1]]
            for label, coordinates in VERTICES.items()
        },
        "edges": edges,
        "edge_weights": {
            f"{edge_start}-{edge_end}": EDGE_DISTANCES[(edge_start, edge_end)]
            for edge_start, edge_end in EDGES
        },
        "labels": LABELS,
        "canvas": {
            "width": WIDTH,
            "height": HEIGHT,
            "node_radius": NODE_RADIUS,
        },
    }
