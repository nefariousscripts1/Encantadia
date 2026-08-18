"""Caesar cipher cryptography and route serialization module.

Provides pure, decoupled functions for:
- Building serialized route messages: PATH|EDGE_WEIGHTS|TOTAL:COST
- Parsing serialized route messages back into structured data
- Single-pass Caesar encryption and decryption for letters and digits
"""

from __future__ import annotations

from typing import Any


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


def parse_route_message(message: str) -> dict[str, Any]:
    """Parse a serialized route message back into its components.

    Input format:
        PATH|EDGE_WEIGHTS|TOTAL:COST
    Returns:
        {"path": list[str], "edge_weights": list[float], "total_cost": float}
    """
    if not isinstance(message, str):
        raise TypeError("Route message must be a string.")

    parts = message.split("|")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid route message format. Expected 3 pipe-separated fields, got {len(parts)}."
        )

    path_str, weights_str, total_str = parts

    path = path_str.split("-") if path_str else []
    edge_weights = [float(w) for w in weights_str.split(",") if w.strip()]

    if not total_str.startswith("TOTAL:"):
        raise ValueError(
            f"Invalid total cost format in route message. Expected 'TOTAL:<cost>', got '{total_str}'."
        )

    try:
        total_cost = float(total_str.replace("TOTAL:", "", 1))
    except ValueError as err:
        raise ValueError(f"Invalid total cost numeric value: {total_str}") from err

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
