"""Automated test suite for GraphCrypt WAYCIPHER A* and Caesar Cipher system."""

import unittest

from app import create_app
from app.cipher import (
    build_route_message,
    caesar_decrypt,
    caesar_encrypt,
    parse_route_message,
)
from app.graph import LABELS, a_star, dijkstra


class GraphCryptWayCipherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def run_astar_api(self, start: str, goal: str, shift: int):
        response = self.client.post(
            "/api/astar",
            json={"start": start, "goal": goal, "shift": shift},
        )
        return response

    # --- Test 1: Map / Cipher Separation ---
    def test_astar_is_cipher_free_and_shift_independent(self):
        """A* must return route data without running the cipher."""
        res_shift3 = self.run_astar_api("A", "T", 3)
        res_shift10 = self.run_astar_api("A", "T", 10)

        self.assertEqual(res_shift3.status_code, 200)
        self.assertEqual(res_shift10.status_code, 200)

        data3 = res_shift3.get_json()
        data10 = res_shift10.get_json()

        # Path must be identical
        expected_path = ["A", "G", "O", "P", "S", "T"]
        self.assertEqual(data3["path"], expected_path)
        self.assertEqual(data10["path"], expected_path)

        # Weights and total cost must be identical
        self.assertEqual(data3["edge_weights"], [195.0, 183.5, 87.4, 124.0, 90.0])
        self.assertEqual(data10["edge_weights"], [195.0, 183.5, 87.4, 124.0, 90.0])
        self.assertEqual(data3["total_cost"], 679.9)
        self.assertEqual(data10["total_cost"], 679.9)

        # Serialized route must be identical
        expected_serialized = "A-G-O-P-S-T|195.0,183.5,87.4,124.0,90.0|TOTAL:679.9"
        self.assertEqual(data3["serialized_route"], expected_serialized)
        self.assertEqual(data10["serialized_route"], expected_serialized)

        # Map responses must not contain cipher state.
        for payload in (data3, data10):
            self.assertNotIn("ciphertext", payload)
            self.assertNotIn("shift", payload)
            self.assertNotIn("cipher_key", payload)
            self.assertEqual(payload["visited_nodes"][0], "A")

    # --- Test 2: Encryption & Decryption Reversibility ---
    def test_caesar_encrypt_and_decrypt_reversibility(self):
        """encrypt(route, shift) then decrypt(ciphertext, shift) must return the exact original route."""
        original_route = "A-G-O-P-S-T|195.0,183.5,87.4,124.0,90.0|TOTAL:679.9"

        for shift in range(26):
            ciphertext = caesar_encrypt(original_route, shift)
            decrypted = caesar_decrypt(ciphertext, shift)
            self.assertEqual(decrypted, original_route)

            parsed = parse_route_message(decrypted)
            self.assertEqual(parsed["path"], ["A", "G", "O", "P", "S", "T"])
            self.assertEqual(parsed["edge_weights"], [195.0, 183.5, 87.4, 124.0, 90.0])
            self.assertEqual(parsed["total_cost"], 679.9)

    # --- Test 3: Plaintext Route Download ---
    def test_download_endpoint_contains_labeled_plaintext_route(self):
        """Downloaded route files must remain plaintext for the Cipher page."""
        response = self.client.post(
            "/api/download",
            json={"start": "A", "goal": "T", "shift": 3},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("route_A_T.txt", response.headers.get("Content-Disposition", ""))

        content = response.data.decode("utf-8")
        self.assertEqual(
            content,
            "Route:\nA-G-O-P-S-T|195.0,183.5,87.4,124.0,90.0|TOTAL:679.9",
        )

    # --- Test 4: A* vs Dijkstra Shortest Path Verification Across All 729 Node Pairs ---
    def test_astar_matches_dijkstra_for_all_pairs(self):
        """Exhaustively verify A* against Dijkstra for all 27x27 node pairs in the graph."""
        for start in LABELS:
            for goal in LABELS:
                astar_res = a_star(start, goal)
                dijkstra_res = dijkstra(start, goal)

                self.assertEqual(
                    astar_res["total_cost"],
                    dijkstra_res["total_cost"],
                    f"Cost mismatch between A* and Dijkstra for {start} -> {goal}",
                )

                if start == goal:
                    self.assertEqual(astar_res["path"], [start])
                else:
                    self.assertEqual(astar_res["path"][0], start)
                    self.assertEqual(astar_res["path"][-1], goal)

    # --- Test 5: Invalid Start / Goal Error Handling ---
    def test_invalid_start_or_goal_returns_error(self):
        """Invalid start or goal node labels must return 400 Bad Request."""
        res_bad_start = self.client.post("/api/astar", json={"start": "INVALID", "goal": "T", "shift": 3})
        self.assertEqual(res_bad_start.status_code, 400)
        self.assertIn("error", res_bad_start.get_json())

        res_bad_goal = self.client.post("/api/astar", json={"start": "A", "goal": "INVALID", "shift": 3})
        self.assertEqual(res_bad_goal.status_code, 400)
        self.assertIn("error", res_bad_goal.get_json())

    # --- Test 6: Cipher Shift Error Handling ---
    def test_invalid_shift_returns_error_from_cipher_endpoints(self):
        """Only Encrypt and Decrypt validate the cipher shift."""
        route = "A-G-O-P-S-T|195.0,183.5,87.4,124.0,90.0|TOTAL:679.9"
        ciphertext = caesar_encrypt(route, 3)
        for endpoint, field, value in (
            ("/api/encrypt", "plaintext", route),
            ("/api/decrypt", "ciphertext", ciphertext),
        ):
            for shift in (-1, 26, "invalid", True, None):
                with self.subTest(endpoint=endpoint, shift=shift):
                    response = self.client.post(
                        endpoint, json={field: value, "shift": shift}
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("shift", response.get_json()["error"].lower())

    # --- Test 7: Application and Map Asset Availability ---
    def test_application_and_map_asset_are_available(self):
        """The backend must continue serving the application and map asset."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        # Check map image endpoint
        map_res = self.client.get("/static/images/argentina_map.png")
        self.assertEqual(map_res.status_code, 200)
        map_res.close()

    # --- Test 8: Decrypt API Endpoint ---
    def test_decrypt_endpoint(self):
        """Test the /api/decrypt endpoint with valid ciphertext."""
        ciphertext = "D-J-R-S-V-W|428.3,416.8,10.7,457.3,23.3|WRWDO:902.2"
        response = self.client.post(
            "/api/decrypt",
            json={"ciphertext": ciphertext, "shift": 3},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["path"], ["A", "G", "O", "P", "S", "T"])
        self.assertEqual(data["edge_weights"], [195.0, 183.5, 87.4, 124.0, 90.0])
        self.assertEqual(data["total_cost"], 679.9)
        self.assertEqual(data["decrypted_message"], "A-G-O-P-S-T|195.0,183.5,87.4,124.0,90.0|TOTAL:679.9")


if __name__ == "__main__":
    unittest.main()
