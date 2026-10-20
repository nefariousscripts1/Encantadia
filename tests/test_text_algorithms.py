"""Correctness and API tests for the text-algorithm laboratory."""

import base64
import random
import unittest

from app import create_app
from app.text_algorithms import (
    HUFFMAN_MAGIC,
    build_lps,
    huffman_compress,
    huffman_decompress,
    kmp_search,
    knapsack_select,
    randomized_quicksort,
    rank_texts,
)


class KMPTests(unittest.TestCase):
    def test_builds_lps_and_finds_expected_positions(self):
        self.assertEqual(build_lps("ABABCABAB"), [0, 0, 1, 2, 0, 1, 2, 3, 4])
        self.assertEqual(kmp_search("ABABDABACDABABCABAB", "ABABCABAB")["matches"], [10])

    def test_overlapping_and_repeated_matches(self):
        self.assertEqual(kmp_search("aaaaa", "aaa")["matches"], [0, 1, 2])
        self.assertEqual(kmp_search("abababa", "aba")["matches"], [0, 2, 4])

    def test_no_match_and_empty_inputs(self):
        self.assertEqual(kmp_search("abcdef", "xyz")["matches"], [])
        self.assertEqual(kmp_search("", "x")["matches"], [])
        self.assertEqual(kmp_search("text", "")["matches"], [])


class HuffmanTests(unittest.TestCase):
    def assert_round_trip(self, text):
        compressed = huffman_compress(text)
        self.assertIsInstance(compressed["data"], bytes)
        self.assertTrue(compressed["data"].startswith(HUFFMAN_MAGIC))
        self.assertEqual(huffman_decompress(compressed["data"])["text"], text)
        self.assertEqual(
            compressed["compressed_size_bytes"],
            compressed["metadata_size_bytes"] + compressed["payload_size_bytes"],
        )

    def test_empty_single_symbol_and_utf8_round_trips(self):
        for text in ("", "xxxxxxxx", "Café — 世界 🌏"):
            with self.subTest(text=text):
                self.assert_round_trip(text)

    def test_rejects_trailing_payload_bytes(self):
        compressed = huffman_compress("valid data")["data"]
        with self.assertRaises(ValueError):
            huffman_decompress(compressed + b"\x00")

    def test_randomized_round_trips(self):
        generator = random.Random(2026)
        alphabet = "abc XYZ 123 ñ界"
        for length in (1, 2, 7, 64, 257):
            text = "".join(generator.choice(alphabet) for _ in range(length))
            self.assert_round_trip(text)

    def test_size_metrics_handle_growth_and_zero_without_division(self):
        empty = huffman_compress("")
        self.assertEqual(empty["compression_ratio"], 0.0)
        self.assertEqual(empty["space_savings_percent"], 0.0)
        tiny = huffman_compress("a")
        self.assertGreater(tiny["compressed_size_bytes"], tiny["original_size_bytes"])
        self.assertLess(tiny["space_savings_percent"], 0)


class KnapsackTests(unittest.TestCase):
    def test_selects_optimal_combination_within_budget(self):
        result = knapsack_select(
            [
                {"name": "A", "cost": 2, "priority": 3},
                {"name": "B", "cost": 3, "priority": 4},
                {"name": "C", "cost": 4, "priority": 5},
            ],
            5,
        )
        self.assertEqual([item["name"] for item in result["selected_items"]], ["A", "B"])
        self.assertEqual(result["total_cost"], 5)
        self.assertEqual(result["total_score"], 7)

    def test_empty_zero_cost_zero_value_and_no_fit_cases(self):
        self.assertEqual(knapsack_select([], 4)["selected_items"], [])
        result = knapsack_select(
            [
                {"name": "Free", "cost": 0, "priority": 5},
                {"name": "Neutral", "cost": 0, "priority": 0},
                {"name": "Large", "cost": 5, "priority": 10},
            ],
            0,
        )
        self.assertEqual([item["name"] for item in result["selected_items"]], ["Free"])
        self.assertEqual(knapsack_select([{"name": "Large", "cost": 5, "priority": 8}], 2)["selected_items"], [])

    def test_is_reproducible(self):
        items = [{"name": "A", "cost": 1, "priority": 1}, {"name": "B", "cost": 1, "priority": 1}]
        self.assertEqual(knapsack_select(items, 1)["selected_items"], knapsack_select(items, 1)["selected_items"])

    def test_rejects_unsafe_budget(self):
        with self.assertRaises(ValueError):
            knapsack_select([{"name": "A", "cost": 1, "priority": 1}], 100_001)


class RandomizedQuickSortTests(unittest.TestCase):
    def test_descending_rank_with_deterministic_name_ties(self):
        values = [
            {"name": "zeta.txt", "match_count": 3},
            {"name": "beta.txt", "match_count": 7},
            {"name": "alpha.txt", "match_count": 7},
            {"name": "none.txt", "match_count": 0},
        ]
        expected = ["alpha.txt", "beta.txt", "zeta.txt", "none.txt"]
        self.assertEqual(
            [item["name"] for item in randomized_quicksort(values, 41)["ranked_results"]],
            expected,
        )
        self.assertEqual(
            randomized_quicksort(values, 41)["ranked_results"],
            randomized_quicksort(values, 41)["ranked_results"],
        )

    def test_empty_sorted_and_reverse_sorted_inputs(self):
        self.assertEqual(randomized_quicksort([], 1)["ranked_results"], [])
        for counts in ([5, 4, 3, 2], [2, 3, 4, 5]):
            values = [{"name": str(index), "match_count": count} for index, count in enumerate(counts)]
            ranked = randomized_quicksort(values, 9)["ranked_results"]
            self.assertEqual([item["match_count"] for item in ranked], [5, 4, 3, 2])

    def test_batch_ranking_uses_kmp(self):
        result = rank_texts(
            [{"name": "two", "text": "aaaa"}, {"name": "one", "text": "baa"}],
            "aa",
            7,
        )
        self.assertEqual([item["match_count"] for item in result["ranked_results"]], [3, 1])


class TextAlgorithmAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def test_kmp_api_and_empty_pattern_validation(self):
        response = self.client.post("/api/text/kmp", json={"text": "banana", "pattern": "ana"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["matches"], [1, 3])
        invalid = self.client.post("/api/text/kmp", json={"text": "banana", "pattern": ""})
        self.assertEqual(invalid.status_code, 400)

    def test_huffman_api_returns_binary_round_trip(self):
        response = self.client.post("/api/text/huffman/compress", json={"text": "résumé résumé"})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["verified"])
        self.assertTrue(base64.b64decode(payload["data_base64"]).startswith(HUFFMAN_MAGIC))
        decoded = self.client.post(
            "/api/text/huffman/decompress", json={"data_base64": payload["data_base64"]}
        )
        self.assertEqual(decoded.get_json()["text"], "résumé résumé")

    def test_knapsack_rank_and_benchmark_apis(self):
        optimized = self.client.post(
            "/api/text/knapsack",
            json={
                "budget": 2,
                "datasets": [
                    {"name": "a.txt", "byte_size": 500, "priority": 4},
                    {"name": "b.txt", "byte_size": 1500, "priority": 7},
                ],
            },
        )
        self.assertEqual(optimized.status_code, 200)
        self.assertEqual(optimized.get_json()["total_score"], 7)

        ranked = self.client.post(
            "/api/text/rank",
            json={
                "pattern": "ana",
                "seed": 12,
                "datasets": [
                    {"name": "first.txt", "text": "banana"},
                    {"name": "second.txt", "text": "plain"},
                ],
            },
        )
        self.assertEqual(ranked.status_code, 200)
        self.assertEqual(ranked.get_json()["ranked_results"][0]["match_count"], 2)

        benchmark = self.client.post("/api/text/benchmark", json={"sizes": [100]})
        self.assertEqual(benchmark.status_code, 200)
        self.assertEqual(len(benchmark.get_json()["rows"]), 4)


if __name__ == "__main__":
    unittest.main()
