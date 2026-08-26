"""Caesar cipher cryptography and route serialization module.

Provides pure, decoupled functions for:
- Building serialized route messages: PATH|EDGE_WEIGHTS|TOTAL:COST
- Parsing serialized route messages back into structured data
- Single-pass Caesar encryption and decryption for letters and digits
"""

from __future__ import annotations

import math
import re
from typing import Any


_NODE_LABEL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


def validate_shift(shift: int) -> int:
    """Validate that the cipher shift is an integer."""
    if isinstance(shift, bool) or not isinstance(shift, int):
        raise TypeError("Cipher shift must be an integer.")
    return shift


def caesar_encrypt(message: str, shift: int) -> str:
    """Encrypt message once using Caesar Cipher.

    Shifts:
    - Uppercase letters 'A'-'Z' by shift % 26
    - Lowercase letters 'a'-'z' by shift % 26
    - Digits '0'-'9' by shift % 10
    - Preserves all separators and punctuation marks (|, -, ,, ., :, etc.)
    """
    if not isinstance(message, str):
        raise TypeError("Message must be a string.")

    shift = validate_shift(shift)
    letter_shift = shift % 26
    digit_shift = shift % 10

    result = []
    for char in message:
        if "A" <= char <= "Z":
            result.append(chr((ord(char) - ord("A") + letter_shift) % 26 + ord("A")))
        elif "a" <= char <= "z":
            result.append(chr((ord(char) - ord("a") + letter_shift) % 26 + ord("a")))
        elif "0" <= char <= "9":
            result.append(str((int(char) + digit_shift) % 10))
        else:
            result.append(char)

    return "".join(result)


def caesar_decrypt(ciphertext: str, shift: int) -> str:
    """Decrypt ciphertext back to plaintext using the same Caesar shift."""
    if not isinstance(ciphertext, str):
        raise TypeError("Ciphertext must be a string.")

    shift = validate_shift(shift)
    return caesar_encrypt(ciphertext, -shift)


def build_route_message(
    path: list[str], weights: list[float], total_cost: float | None = None
) -> str:
    """Serialize the shortest path route into WAYCIPHER format.

    Format:
        PATH|EDGE_WEIGHTS|TOTAL:COST
    Example:
        A-G-O-P-S-T|195.0,183.5,87.4,124.0,90.0|TOTAL:679.9
    """
    path_str = "-".join(path) if path else ""
    weights_str = ",".join(f"{float(w):.1f}" for w in weights)

    if total_cost is None:
        total_cost = round(sum(weights), 1) if weights else 0.0

    return f"{path_str}|{weights_str}|TOTAL:{float(total_cost):.1f}"


def normalize_labeled_text(text: str, label: str) -> str:
    """Trim uploaded text and remove one optional leading ``<label>:`` marker.

    Text files written with a UTF-8 byte-order mark are accepted.  Only a
    leading label is removed, so occurrences inside the serialized payload are
    left untouched.
    """
    if not isinstance(text, str):
        raise TypeError("Uploaded content must be a string.")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("Payload label must be a non-empty string.")

    normalized = text.strip()
    if normalized.startswith("\ufeff"):
        normalized = normalized[1:].strip()

    label_pattern = re.compile(rf"^{re.escape(label.strip())}\s*:\s*", re.IGNORECASE)
    normalized = label_pattern.sub("", normalized, count=1).strip()
    return normalized


def _parse_route_number(value: str, field_name: str) -> float:
    """Parse a finite integer-or-decimal route value with a clear error."""
    normalized = value.strip()
    if not normalized or not _NUMBER_PATTERN.fullmatch(normalized):
        raise ValueError(f"Invalid {field_name} numeric value: '{value}'.")

    parsed = float(normalized)
    if not math.isfinite(parsed):
        raise ValueError(f"Invalid {field_name} numeric value: '{value}'.")
    return parsed


def parse_route_message(message: str) -> dict[str, Any]:
    """Parse a serialized route message back into its components.

    Input format:
        PATH|EDGE_WEIGHTS|TOTAL:COST
    Returns:
        {"path": list[str], "edge_weights": list[float], "total_cost": float}
    """
    if not isinstance(message, str):
        raise TypeError("Route message must be a string.")

    message = message.strip()
    if not message:
        raise ValueError("Route message is empty.")

    parts = message.split("|")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid route message format. Expected 3 pipe-separated fields, got {len(parts)}."
        )

    path_str, weights_str, total_str = (part.strip() for part in parts)

    if not path_str:
        raise ValueError("Route path must contain at least one node.")

    path = [node.strip() for node in path_str.split("-")]
    if any(not node or not _NODE_LABEL_PATTERN.fullmatch(node) for node in path):
        raise ValueError("Route path contains an invalid node label.")

    if weights_str:
        weight_values = weights_str.split(",")
        if any(not value.strip() for value in weight_values):
            raise ValueError("Route edge weights cannot contain empty values.")
        edge_weights = [
            _parse_route_number(value, "edge weight") for value in weight_values
        ]
    else:
        edge_weights = []

    expected_weight_count = len(path) - 1
    if len(edge_weights) != expected_weight_count:
        raise ValueError(
            "Route edge-weight count must equal the number of path edges "
            f"({expected_weight_count}); got {len(edge_weights)}."
        )
    if any(weight < 0 for weight in edge_weights):
        raise ValueError("Route edge weights cannot be negative.")

    if not total_str.startswith("TOTAL:"):
        raise ValueError(
            f"Invalid total cost format in route message. Expected 'TOTAL:<cost>', got '{total_str}'."
        )

    total_value = total_str.replace("TOTAL:", "", 1)
    total_cost = _parse_route_number(total_value, "total cost")
    if total_cost < 0:
        raise ValueError("Route total cost cannot be negative.")

    expected_total = math.fsum(edge_weights)
    if not math.isclose(total_cost, expected_total, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError(
            "Route total cost does not equal the sum of its edge weights "
            f"({expected_total:g})."
        )

    return {
        "path": path,
        "edge_weights": edge_weights,
        "total_cost": round(total_cost, 1),
    }


# Backward compatibility aliases
def encrypt_text(text: str, key: int) -> str:
    return caesar_encrypt(text, key)


def decrypt_text(encrypted_text: str, key: int) -> str:
    return caesar_decrypt(encrypted_text, key)


def encrypt_weight(weight: float | str, key: int) -> str:
    if isinstance(weight, (int, float)):
        weight = f"{weight:.1f}"
    return caesar_encrypt(str(weight), key)


def decrypt_weight(encrypted_weight: float | str, key: int) -> str:
    return caesar_decrypt(str(encrypted_weight), key)
