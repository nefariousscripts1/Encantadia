"""Independent correctness and trace audit for GraphCrypt A* pathfinding.

The oracle in this module intentionally does not call ``app.graph.dijkstra``
or reuse the production adjacency matrix.  It builds its own graph from the
canonical edge definitions and runs an independent Dijkstra implementation.
"""

from __future__ import annotations

import heapq
import math
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from app import create_app
import app.graph as graph


TOLERANCE = 1e-6
PROJECT_ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve()


def build_independent_adjacency() -> dict[str, list[tuple[str, float]]]:
    """Build an oracle adjacency list without using production ADJACENCY."""
    adjacency = {label: [] for label in graph.LABELS}
    for edge_start, edge_end, weight in graph.EDGE_DEFINITIONS:
        adjacency[edge_start].append((edge_end, weight))
        adjacency[edge_end].append((edge_start, weight))
    return adjacency


ORACLE_ADJACENCY = build_independent_adjacency()
ORACLE_EDGE_WEIGHTS = {
    frozenset((edge_start, edge_end)): weight
    for edge_start, edge_end, weight in graph.EDGE_DEFINITIONS
}


def independent_dijkstra(start: str, goal: str) -> dict[str, object]:
    """Return one independently computed shortest path and its exact cost."""
    if start not in ORACLE_ADJACENCY:
        raise ValueError(f"Unknown oracle start node: {start}")
    if goal not in ORACLE_ADJACENCY:
        raise ValueError(f"Unknown oracle goal node: {goal}")
    if start == goal:
        return {"path": [start], "total_cost": 0.0}

    distances = {label: math.inf for label in ORACLE_ADJACENCY}
    distances[start] = 0.0
    predecessor: dict[str, str] = {}
    sequence = 0
    queue: list[tuple[float, int, str]] = [(0.0, sequence, start)]

    while queue:
        current_distance, _, current = heapq.heappop(queue)
        if current_distance > distances[current] + TOLERANCE:
            continue
        if current == goal:
            break

        for neighbor, weight in ORACLE_ADJACENCY[current]:
            candidate = current_distance + weight
            if candidate + TOLERANCE < distances[neighbor]:
                distances[neighbor] = candidate
                predecessor[neighbor] = current
                sequence += 1
                heapq.heappush(queue, (candidate, sequence, neighbor))

    if math.isinf(distances[goal]):
        return {"path": [], "total_cost": None}

    path = [goal]
    while path[-1] != start:
        path.append(predecessor[path[-1]])
    path.reverse()
    return {"path": path, "total_cost": distances[goal]}


def discover_named_path4_references() -> list[str]:
    """Find real path4/Path 4 references while excluding this QA test itself."""
    pattern = re.compile(r"\b(?:path\s*4|path4)\b", re.IGNORECASE)
    ignored_directories = {".git", "venv", ".venv", "__pycache__", ".pytest_cache"}
    searchable_suffixes = {".py", ".js", ".html", ".css", ".md", ".json", ".txt"}
    matches: list[str] = []

    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == THIS_FILE:
            continue
        if any(part in ignored_directories for part in path.parts):
            continue
        if path.suffix.lower() not in searchable_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                matches.append(f"{path.relative_to(PROJECT_ROOT)}:{line_number}: {line.strip()}")
    return matches


class AStarIndependentOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.oracle_results = {
            (start, goal): independent_dijkstra(start, goal)
            for start in graph.LABELS
            for goal in graph.LABELS
        }

    def pair_context(
        self,
        start: str,
        goal: str,
        astar_result: dict[str, object],
        oracle_result: dict[str, object],
    ) -> str:
        return (
            f"start={start}, goal={goal}; "
            f"A* path={astar_result['path']}, cost={astar_result['total_cost']}; "
            f"Dijkstra path={oracle_result['path']}, cost={oracle_result['total_cost']}"
        )

    def assert_valid_astar_route(
        self,
        start: str,
        goal: str,
        astar_result: dict[str, object],
        oracle_result: dict[str, object],
    ) -> None:
        context = self.pair_context(start, goal, astar_result, oracle_result)
        oracle_cost = oracle_result["total_cost"]

        if oracle_cost is None:
            self.assertEqual(astar_result["path"], [], context)
            self.assertIsNone(astar_result["total_cost"], context)
            self.assertEqual(astar_result["edge_weights"], [], context)
            self.assertEqual(astar_result["path_edges"], [], context)
            return

        path = astar_result["path"]
        self.assertTrue(path, context)
        self.assertEqual(path[0], start, context)
        self.assertEqual(path[-1], goal, context)
        self.assertEqual(len(path), len(set(path)), f"Repeated node/loop. {context}")

        if start == goal:
            self.assertEqual(path, [start], context)
            self.assertAlmostEqual(astar_result["total_cost"], 0.0, delta=TOLERANCE, msg=context)
            self.assertEqual(astar_result["edge_weights"], [], context)
            self.assertEqual(astar_result["path_edges"], [], context)
            return

        self.assertEqual(len(astar_result["edge_weights"]), len(path) - 1, context)
        self.assertEqual(len(astar_result["path_edges"]), len(path) - 1, context)

        actual_weights: list[float] = []
        for index, (edge_start, edge_end) in enumerate(zip(path, path[1:])):
            edge_key = frozenset((edge_start, edge_end))
            self.assertIn(edge_key, ORACLE_EDGE_WEIGHTS, f"Missing real edge {edge_start}-{edge_end}. {context}")
            actual_weight = ORACLE_EDGE_WEIGHTS[edge_key]
            actual_weights.append(actual_weight)
            self.assertAlmostEqual(
                astar_result["edge_weights"][index],
                actual_weight,
                delta=TOLERANCE,
                msg=f"Wrong edge weight for {edge_start}-{edge_end}. {context}",
            )
            self.assertEqual(
                astar_result["path_edges"][index],
                {"from": edge_start, "to": edge_end, "weight": actual_weight},
                context,
            )

        recomputed_cost = math.fsum(actual_weights)
        self.assertAlmostEqual(astar_result["total_cost"], recomputed_cost, delta=TOLERANCE, msg=context)
        self.assertAlmostEqual(astar_result["total_cost"], oracle_cost, delta=TOLERANCE, msg=context)

    def test_graph_data_structures_match_canonical_edge_definitions(self):
        self.assertEqual(len(graph.LABELS), 27)
        self.assertEqual(len(graph.EDGE_DEFINITIONS), 40)
        self.assertEqual(len(ORACLE_EDGE_WEIGHTS), 40)

        for edge_start, edge_end, weight in graph.EDGE_DEFINITIONS:
            self.assertIn(edge_start, graph.LABELS)
            self.assertIn(edge_end, graph.LABELS)
            self.assertNotEqual(edge_start, edge_end)
            self.assertGreater(weight, 0.0)
            self.assertAlmostEqual(graph.EDGE_DISTANCES[(edge_start, edge_end)], weight, delta=TOLERANCE)
            self.assertAlmostEqual(graph.EDGE_DISTANCES[(edge_end, edge_start)], weight, delta=TOLERANCE)
            self.assertAlmostEqual(
                graph.ADJACENCY[graph.INDEX[edge_start]][graph.INDEX[edge_end]],
                weight,
                delta=TOLERANCE,
            )
            self.assertAlmostEqual(
                graph.ADJACENCY[graph.INDEX[edge_end]][graph.INDEX[edge_start]],
                weight,
                delta=TOLERANCE,
            )

    def test_f_to_v_route_weights_cost_api_and_node_count(self):
        expected_path = ["F", "M", "L", "T", "S", "P", "O", "N", "V"]
        expected_weights = [153.6, 78.4, 175.8, 90.0, 124.0, 87.4, 93.6, 43.2]
        expected_cost = 846.0

        oracle_result = self.oracle_results[("F", "V")]
        astar_result = graph.a_star("F", "V")
        context = self.pair_context("F", "V", astar_result, oracle_result)

        self.assertEqual(oracle_result["path"], expected_path, context)
        self.assertAlmostEqual(oracle_result["total_cost"], expected_cost, delta=TOLERANCE, msg=context)
        self.assertEqual(astar_result["path"], expected_path, context)
        self.assertEqual(len(astar_result["path"]), 9, context)
        self.assertEqual(astar_result["edge_weights"], expected_weights, context)
        self.assertAlmostEqual(math.fsum(expected_weights), expected_cost, delta=TOLERANCE, msg=context)
        self.assert_valid_astar_route("F", "V", astar_result, oracle_result)

        response = self.client.post("/api/astar", json={"start": "F", "goal": "V", "shift": 3})
        self.assertEqual(response.status_code, 200, context)
        payload = response.get_json()
        for key in ("path", "edge_weights", "total_cost", "start_cost", "explored", "path_edges"):
            self.assertEqual(payload[key], astar_result[key], f"API field mismatch: {key}. {context}")

    def test_all_729_pairs_match_independent_dijkstra_and_return_valid_routes(self):
        unreachable_pairs = 0
        for start in graph.LABELS:
            for goal in graph.LABELS:
                astar_result = graph.a_star(start, goal)
                oracle_result = self.oracle_results[(start, goal)]
                if oracle_result["total_cost"] is None:
                    unreachable_pairs += 1
                self.assert_valid_astar_route(start, goal, astar_result, oracle_result)

        # The production graph is connected; unreachable handling is exercised separately.
        self.assertEqual(unreachable_pairs, 0)

    def test_every_direct_neighbor_pair_matches_the_oracle(self):
        direct_optimal_routes = 0
        for edge_start, edge_end, direct_weight in graph.EDGE_DEFINITIONS:
            for start, goal in ((edge_start, edge_end), (edge_end, edge_start)):
                astar_result = graph.a_star(start, goal)
                oracle_result = self.oracle_results[(start, goal)]
                self.assert_valid_astar_route(start, goal, astar_result, oracle_result)
                if math.isclose(oracle_result["total_cost"], direct_weight, abs_tol=TOLERANCE):
                    direct_optimal_routes += 1
                    self.assertEqual(astar_result["path"], [start, goal])
        self.assertGreater(direct_optimal_routes, 0)

    def test_start_equals_goal_for_every_node(self):
        for node in graph.LABELS:
            astar_result = graph.a_star(node, node)
            self.assert_valid_astar_route(node, node, astar_result, self.oracle_results[(node, node)])
            self.assertAlmostEqual(astar_result["start_cost"]["h"], 0.0, delta=TOLERANCE)

    def test_unreachable_goal_contract_with_isolated_goal(self):
        isolated_adjacency = [row[:] for row in graph.ADJACENCY]
        goal_index = graph.INDEX["V"]
        for index in range(len(graph.LABELS)):
            isolated_adjacency[goal_index][index] = 0.0
            isolated_adjacency[index][goal_index] = 0.0

        with patch.object(graph, "ADJACENCY", isolated_adjacency):
            result = graph.a_star("F", "V")

        self.assertEqual(result["path"], [])
        self.assertEqual(result["edge_weights"], [])
        self.assertIsNone(result["total_cost"])
        self.assertEqual(result["path_edges"], [])

    def test_equal_cost_tied_routes_accept_either_optimal_path(self):
        synthetic_adjacency = [[0.0] * len(graph.LABELS) for _ in graph.LABELS]
        synthetic_edges: dict[tuple[str, str], float] = {}
        for edge_start, edge_end in (("A", "B"), ("B", "H"), ("A", "G"), ("G", "H")):
            start_index = graph.INDEX[edge_start]
            end_index = graph.INDEX[edge_end]
            synthetic_adjacency[start_index][end_index] = 1.0
            synthetic_adjacency[end_index][start_index] = 1.0
            synthetic_edges[(edge_start, edge_end)] = 1.0
            synthetic_edges[(edge_end, edge_start)] = 1.0

        with (
            patch.object(graph, "ADJACENCY", synthetic_adjacency),
            patch.object(graph, "EDGE_DISTANCES", synthetic_edges),
            patch.object(graph, "heuristic", return_value=0.0),
        ):
            result = graph.a_star("A", "H")

        self.assertIn(result["path"], (["A", "B", "H"], ["A", "G", "H"]))
        self.assertAlmostEqual(result["total_cost"], 2.0, delta=TOLERANCE)
        self.assertEqual(result["edge_weights"], [1.0, 1.0])

    def test_stale_goal_queue_entry_cannot_override_a_better_route(self):
        synthetic_adjacency = [[0.0] * len(graph.LABELS) for _ in graph.LABELS]
        synthetic_edges: dict[tuple[str, str], float] = {}
        for edge_start, edge_end, weight in (("A", "H", 100.0), ("A", "B", 1.0), ("B", "H", 1.0)):
            start_index = graph.INDEX[edge_start]
            end_index = graph.INDEX[edge_end]
            synthetic_adjacency[start_index][end_index] = weight
            synthetic_adjacency[end_index][start_index] = weight
            synthetic_edges[(edge_start, edge_end)] = weight
            synthetic_edges[(edge_end, edge_start)] = weight

        with (
            patch.object(graph, "ADJACENCY", synthetic_adjacency),
            patch.object(graph, "EDGE_DISTANCES", synthetic_edges),
            patch.object(graph, "heuristic", return_value=0.0),
        ):
            result = graph.a_star("A", "H")

        self.assertEqual(result["path"], ["A", "B", "H"])
        self.assertAlmostEqual(result["total_cost"], 2.0, delta=TOLERANCE)
        self.assertEqual(result["edge_weights"], [1.0, 1.0])

    def test_heuristic_is_zero_nonnegative_admissible_and_consistent(self):
        for goal in graph.LABELS:
            self.assertAlmostEqual(graph.heuristic(goal, goal), 0.0, delta=TOLERANCE)

            for node in graph.LABELS:
                estimate = graph.heuristic(node, goal)
                actual_distance = self.oracle_results[(node, goal)]["total_cost"]
                self.assertGreaterEqual(estimate, -TOLERANCE, f"Negative h({node}, {goal})")
                self.assertIsNotNone(actual_distance)
                self.assertLessEqual(
                    estimate,
                    actual_distance + TOLERANCE,
                    f"Inadmissible h({node}, {goal})={estimate}; actual={actual_distance}",
                )

            for edge_start, edge_end, weight in graph.EDGE_DEFINITIONS:
                for node, neighbor in ((edge_start, edge_end), (edge_end, edge_start)):
                    node_h = graph.heuristic(node, goal)
                    neighbor_h = graph.heuristic(neighbor, goal)
                    self.assertLessEqual(
                        node_h,
                        weight + neighbor_h + TOLERANCE,
                        (
                            f"Inconsistent heuristic for goal={goal}, edge={node}-{neighbor}: "
                            f"h({node})={node_h}, weight={weight}, h({neighbor})={neighbor_h}"
                        ),
                    )

    def test_every_trace_entry_has_exact_g_h_and_f_values(self):
        for start in graph.LABELS:
            for goal in graph.LABELS:
                astar_result = graph.a_star(start, goal)
                oracle_result = self.oracle_results[(start, goal)]
                context = self.pair_context(start, goal, astar_result, oracle_result)

                start_h = graph.heuristic(start, goal)
                self.assertAlmostEqual(astar_result["start_cost"]["g"], 0.0, delta=TOLERANCE, msg=context)
                self.assertAlmostEqual(astar_result["start_cost"]["h"], start_h, delta=TOLERANCE, msg=context)
                self.assertAlmostEqual(
                    astar_result["start_cost"]["f"],
                    astar_result["start_cost"]["g"] + astar_result["start_cost"]["h"],
                    delta=TOLERANCE,
                    msg=context,
                )

                best_g = {label: math.inf for label in graph.LABELS}
                best_g[start] = 0.0
                trace_edges: set[tuple[str, str]] = set()
                for entry in astar_result["explored"]:
                    edge = (entry["from"], entry["to"])
                    trace_edges.add(edge)
                    self.assertIn(frozenset(edge), ORACLE_EDGE_WEIGHTS, context)
                    actual_weight = ORACLE_EDGE_WEIGHTS[frozenset(edge)]
                    self.assertAlmostEqual(entry["weight"], actual_weight, delta=TOLERANCE, msg=context)
                    self.assertFalse(math.isinf(best_g[entry["from"]]), context)

                    expected_g = best_g[entry["from"]] + actual_weight
                    expected_h = graph.heuristic(entry["to"], goal)
                    expected_f = expected_g + expected_h
                    self.assertLess(expected_g, best_g[entry["to"]] + TOLERANCE, context)
                    self.assertAlmostEqual(entry["g"], expected_g, delta=TOLERANCE, msg=context)
                    self.assertAlmostEqual(entry["h"], expected_h, delta=TOLERANCE, msg=context)
                    self.assertAlmostEqual(entry["f"], expected_f, delta=TOLERANCE, msg=context)
                    self.assertAlmostEqual(entry["f"], entry["g"] + entry["h"], delta=TOLERANCE, msg=context)
                    best_g[entry["to"]] = expected_g

                for path_edge in astar_result["path_edges"]:
                    self.assertIn((path_edge["from"], path_edge["to"]), trace_edges, context)

    def test_api_trace_and_frontend_display_use_the_returned_result(self):
        direct_result = graph.a_star("F", "V")
        response = self.client.post("/api/astar", json={"start": "F", "goal": "V", "shift": 3})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["path"], direct_result["path"])
        self.assertEqual(payload["total_cost"], direct_result["total_cost"])
        self.assertEqual(payload["explored"], direct_result["explored"])
        self.assertEqual(payload["path_edges"], direct_result["path_edges"])

        frontend = (PROJECT_ROOT / "app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        for required_contract in (
            "for (const edge of result.explored)",
            "for (const edge of result.path_edges)",
            'result.path.join(" → ")',
            "result.total_cost.toFixed(1)",
            "const pathNodes = result.path",
        ):
            self.assertIn(required_contract, frontend)

    def test_path4_named_feature_is_explicitly_absent(self):
        references = discover_named_path4_references()
        self.assertEqual(
            references,
            [],
            "A path4/Path 4 feature now exists and needs explicit sequence/edge/cost validation:\n"
            + "\n".join(references),
        )


if __name__ == "__main__":
    unittest.main()
