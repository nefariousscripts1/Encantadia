"""Focused tests for GraphCrypt's separated route-file cipher endpoints."""

import unittest
from unittest.mock import patch

from app import create_app
from app.cipher import (
    build_route_message,
    caesar_decrypt,
    caesar_encrypt,
    normalize_labeled_text,
    parse_route_message,
)


ROUTE = "A-G-O-P-S-T|195.0,183.5,87.4,124.0,90.0|TOTAL:679.9"
CIPHERTEXT_SHIFT_3 = "D-J-R-S-V-W|428.3,416.8,10.7,457.3,23.3|WRWDO:902.2"


class CipherRouteEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    def test_download_encrypt_and_labeled_decrypt_round_trip(self):
        download_response = self.client.post(
            "/api/download", json={"start": "A", "goal": "T"}
        )
        self.assertEqual(download_response.status_code, 200)
        route_file = download_response.data.decode("utf-8")
        self.assertEqual(route_file, f"Route:\n{ROUTE}")

        encrypt_response = self.client.post(
            "/api/encrypt",
            json={
                "plaintext": f"\n\ufeff Route :\r\n{ROUTE}\r\n",
                "shift": "03",
                "filename": "route_A_T.TXT",
            },
        )
        self.assertEqual(encrypt_response.status_code, 200)
        encrypted = encrypt_response.get_json()
        self.assertEqual(encrypted["plaintext"], ROUTE)
        self.assertEqual(encrypted["serialized_route"], ROUTE)
        self.assertEqual(encrypted["ciphertext"], CIPHERTEXT_SHIFT_3)
        self.assertEqual(encrypted["path"], ["A", "G", "O", "P", "S", "T"])
        self.assertEqual(encrypted["total_cost"], 679.9)
        self.assertEqual(encrypted["shift"], 3)
        self.assertEqual(encrypted["cipher_key"], 3)

        decrypt_response = self.client.post(
            "/api/decrypt",
            json={
                "ciphertext": (
                    f"\r\n\ufeffCiphertext:\r\n{encrypted['ciphertext']}\r\n"
                ),
                "cipher_key": "3",
                "filename": "encrypted_route.txt",
            },
        )
        self.assertEqual(decrypt_response.status_code, 200)
        decrypted = decrypt_response.get_json()
        self.assertEqual(decrypted["ciphertext"], CIPHERTEXT_SHIFT_3)
        self.assertEqual(decrypted["decrypted_message"], ROUTE)
        self.assertEqual(decrypted["plaintext"], ROUTE)
        self.assertEqual(decrypted["serialized_route"], ROUTE)
        self.assertEqual(decrypted["path"], ["A", "G", "O", "P", "S", "T"])
        self.assertEqual(
            decrypted["edge_weights"], [195.0, 183.5, 87.4, 124.0, 90.0]
        )
        self.assertEqual(decrypted["total_cost"], 679.9)
        self.assertEqual(decrypted["shift"], 3)
        self.assertEqual(decrypted["cipher_key"], 3)

    def test_unreachable_map_routes_return_clear_errors(self):
        disconnected_result = {
            "path": [],
            "edge_weights": [],
            "total_cost": None,
            "start_cost": {"g": 0.0, "h": 1.0, "f": 1.0},
            "explored": [],
            "path_edges": [],
        }

        with patch("app.routes.a_star", return_value=disconnected_result):
            for endpoint in ("/api/astar", "/api/download"):
                with self.subTest(endpoint=endpoint):
                    response = self.client.post(
                        endpoint, json={"start": "A", "goal": "T"}
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("No route exists", response.get_json()["error"])

    def test_route_alias_and_shift_boundaries(self):
        for shift in (0, 25):
            with self.subTest(shift=shift):
                encrypted_response = self.client.post(
                    "/api/encrypt", json={"route": ROUTE, "shift": shift}
                )
                self.assertEqual(encrypted_response.status_code, 200)
                ciphertext = encrypted_response.get_json()["ciphertext"]
                self.assertEqual(ciphertext, caesar_encrypt(ROUTE, shift))

                decrypted_response = self.client.post(
                    "/api/decrypt",
                    json={"ciphertext": ciphertext, "shift": shift},
                )
                self.assertEqual(decrypted_response.status_code, 200)
                self.assertEqual(
                    decrypted_response.get_json()["decrypted_message"], ROUTE
                )

    def test_cipher_endpoints_reject_invalid_or_missing_shifts(self):
        invalid_shifts = (-1, 26, "-1", "+26", "3.0", "invalid", True, None)
        for endpoint, content_field, content in (
            ("/api/encrypt", "plaintext", ROUTE),
            ("/api/decrypt", "ciphertext", CIPHERTEXT_SHIFT_3),
        ):
            for shift in invalid_shifts:
                with self.subTest(endpoint=endpoint, shift=shift):
                    response = self.client.post(
                        endpoint,
                        json={content_field: content, "shift": shift},
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("shift", response.get_json()["error"].lower())

            missing_response = self.client.post(
                endpoint, json={content_field: content}
            )
            self.assertEqual(missing_response.status_code, 400)
            self.assertIn("shift", missing_response.get_json()["error"].lower())

    def test_manual_text_endpoints_round_trip_without_route_parsing(self):
        cases = (
            ("HELLO WORLD", 3, "KHOOR ZRUOG"),
            ("Hello World 123!", 3, "Khoor Zruog 456!"),
            ("Abc xyz 789!? @#", 3, "Def abc 012!? @#"),
            ("Mixed CASE\nSecond line.", 25, caesar_encrypt("Mixed CASE\nSecond line.", 25)),
        )

        for plaintext, shift, expected_ciphertext in cases:
            with self.subTest(plaintext=plaintext, shift=shift):
                encrypted_response = self.client.post(
                    "/api/encrypt-text",
                    json={"plaintext": plaintext, "shift": shift},
                )
                self.assertEqual(encrypted_response.status_code, 200)
                encrypted = encrypted_response.get_json()
                self.assertEqual(encrypted["ciphertext"], expected_ciphertext)
                self.assertEqual(encrypted["plaintext"], plaintext)
                self.assertEqual(encrypted["shift"], shift)

                decrypted_response = self.client.post(
                    "/api/decrypt-text",
                    json={"ciphertext": encrypted["ciphertext"], "shift": shift},
                )
                self.assertEqual(decrypted_response.status_code, 200)
                decrypted = decrypted_response.get_json()
                self.assertEqual(decrypted["decrypted_message"], plaintext)
                self.assertEqual(decrypted["plaintext"], plaintext)
                self.assertEqual(decrypted["shift"], shift)

    def test_manual_text_upload_labels_validation_and_shift_boundaries(self):
        encrypted_response = self.client.post(
            "/api/encrypt-text",
            json={
                "plaintext": "Plaintext:\nHELLO WORLD",
                "shift": "03",
                "filename": "plain.TXT",
            },
        )
        self.assertEqual(encrypted_response.status_code, 200)
        self.assertEqual(encrypted_response.get_json()["ciphertext"], "KHOOR ZRUOG")

        decrypted_response = self.client.post(
            "/api/decrypt-text",
            json={
                "ciphertext": "Ciphertext:\r\nKHOOR ZRUOG",
                "shift": 3,
                "filename": "encrypted.txt",
            },
        )
        self.assertEqual(decrypted_response.status_code, 200)
        self.assertEqual(decrypted_response.get_json()["plaintext"], "HELLO WORLD")

        for endpoint, field in (
            ("/api/encrypt-text", "plaintext"),
            ("/api/decrypt-text", "ciphertext"),
        ):
            for empty_value in ("", "   \r\n"):
                with self.subTest(endpoint=endpoint, empty_value=repr(empty_value)):
                    response = self.client.post(
                        endpoint,
                        json={field: empty_value, "shift": 3},
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("empty", response.get_json()["error"].lower())

            for invalid_shift in (-1, 26, "3.5", True, None):
                with self.subTest(endpoint=endpoint, invalid_shift=invalid_shift):
                    response = self.client.post(
                        endpoint,
                        json={field: "HELLO", "shift": invalid_shift},
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("shift", response.get_json()["error"].lower())

            invalid_file_response = self.client.post(
                endpoint,
                json={field: "HELLO", "shift": 3, "filename": "message.csv"},
            )
            self.assertEqual(invalid_file_response.status_code, 400)
            self.assertIn(".txt", invalid_file_response.get_json()["error"])

    def test_invalid_request_shapes_payload_types_and_file_extensions(self):
        for endpoint in ("/api/encrypt", "/api/decrypt"):
            response = self.client.post(endpoint, json=["not", "an", "object"])
            self.assertEqual(response.status_code, 400)
            self.assertIn("JSON object", response.get_json()["error"])

            field = "plaintext" if endpoint.endswith("encrypt") else "ciphertext"
            content = ROUTE if field == "plaintext" else CIPHERTEXT_SHIFT_3
            response = self.client.post(
                endpoint,
                json={field: content, "shift": 3, "filename": "route.csv"},
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(".txt", response.get_json()["error"])

            response = self.client.post(
                endpoint,
                json={field: 123, "shift": 3, "filename": "route.txt"},
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("string", response.get_json()["error"])

    def test_empty_and_malformed_route_files_return_clear_errors(self):
        for value in ("", "  \r\n ", "Route:\n", "\ufeff route : \n"):
            with self.subTest(value=repr(value)):
                response = self.client.post(
                    "/api/encrypt", json={"plaintext": value, "shift": 3}
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("empty", response.get_json()["error"].lower())

        malformed_routes = (
            "not a serialized route",
            "A-B||TOTAL:0.0",
            "A--B|1.0|TOTAL:1.0",
            "A-B|-1.0|TOTAL:-1.0",
            "A-B|1.0|TOTAL:2.0",
            "A-B|one|TOTAL:1.0",
        )
        for route in malformed_routes:
            with self.subTest(route=route):
                response = self.client.post(
                    "/api/encrypt", json={"plaintext": route, "shift": 3}
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("invalid route file", response.get_json()["error"].lower())

    def test_empty_malformed_and_wrong_key_ciphertext_return_clear_errors(self):
        for value in ("", " \n", "Ciphertext:\n", "\ufeff ciphertext :\r\n"):
            with self.subTest(value=repr(value)):
                response = self.client.post(
                    "/api/decrypt", json={"ciphertext": value, "shift": 3}
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("empty", response.get_json()["error"].lower())

        for ciphertext, shift in (
            ("not ciphertext", 0),
            ("A-B|1.0|TOTAL:2.0", 0),
            (CIPHERTEXT_SHIFT_3, 4),
        ):
            with self.subTest(ciphertext=ciphertext, shift=shift):
                response = self.client.post(
                    "/api/decrypt",
                    json={"ciphertext": ciphertext, "shift": shift},
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("selected shift", response.get_json()["error"].lower())


class CipherSerializationTests(unittest.TestCase):
    def test_optional_labels_and_strict_route_parser(self):
        self.assertEqual(normalize_labeled_text(f"Route:\n{ROUTE}", "Route"), ROUTE)
        self.assertEqual(
            normalize_labeled_text(f"ciphertext: {CIPHERTEXT_SHIFT_3}", "Ciphertext"),
            CIPHERTEXT_SHIFT_3,
        )
        parsed = parse_route_message(ROUTE)
        self.assertEqual(parsed["path"], ["A", "G", "O", "P", "S", "T"])
        self.assertEqual(parsed["total_cost"], 679.9)

        for malformed in (
            "",
            "A-B|1.0",
            "A-B|1.0|COST:1.0",
            "A-B-C|1.0|TOTAL:1.0",
            "A-B|1.0|TOTAL:nan",
            "A-B|1.0|TOTAL:2.0",
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(ValueError):
                    parse_route_message(malformed)

    def test_caesar_reversibility_and_separator_preservation(self):
        separators = "|-,:.\n "
        for shift in range(26):
            with self.subTest(shift=shift):
                ciphertext = caesar_encrypt(ROUTE, shift)
                self.assertEqual(caesar_decrypt(ciphertext, shift), ROUTE)
                self.assertEqual(
                    "".join(char for char in ciphertext if char in separators),
                    "".join(char for char in ROUTE if char in separators),
                )

    def test_build_and_parse_single_node_route(self):
        serialized = build_route_message(["Z1"], [], 0)
        self.assertEqual(serialized, "Z1||TOTAL:0.0")
        self.assertEqual(
            parse_route_message(serialized),
            {"path": ["Z1"], "edge_weights": [], "total_cost": 0.0},
        )


if __name__ == "__main__":
    unittest.main()
