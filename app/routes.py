"""Flask routes for GraphCrypt's separated map and cipher workflows."""

from __future__ import annotations

from io import BytesIO
import re
from typing import Any

from flask import Blueprint, jsonify, render_template, request, send_file

from .cipher import (
    build_route_message,
    caesar_decrypt,
    caesar_encrypt,
    normalize_labeled_text,
    parse_route_message,
    validate_shift,
)
from .graph import LABELS, a_star, graph_payload


main = Blueprint("main", __name__)


@main.get("/")
def index():
    """Render the GraphCrypt visualizer interface."""
    return render_template("index.html")


@main.get("/api/graph")
def get_graph():
    """Return nodes, coordinates, weighted edges, and canvas dimensions."""
    return jsonify(graph_payload())


def _extract_route_parameters() -> tuple[tuple[str, str] | None, Any | None]:
    """Validate incoming map request parameters without involving a cipher key."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        # Check query parameters as fallback
        data = request.args.to_dict() if request.args else {}

    if not isinstance(data, dict):
        return None, (jsonify(error="Request body must be a JSON object."), 400)

    start = data.get("start")
    goal = data.get("goal")

    if not isinstance(start, str) or not isinstance(goal, str):
        return None, (jsonify(error="Both start and goal must be node labels."), 400)

    if start not in LABELS:
        return None, (jsonify(error=f"Invalid start node: {start}", valid_nodes=LABELS), 400)

    if goal not in LABELS:
        return None, (jsonify(error=f"Invalid goal node: {goal}", valid_nodes=LABELS), 400)

    return (start, goal), None


def _extract_shift(data: dict[str, Any]) -> tuple[int | None, Any | None]:
    """Read and validate a user-facing Caesar shift in the supported range."""
    shift: Any = data.get("shift", data.get("cipher_key"))
    if isinstance(shift, str):
        shift = shift.strip()
        if re.fullmatch(r"[+-]?\d+", shift):
            shift = int(shift)

    try:
        shift = validate_shift(shift)
    except TypeError:
        return None, (jsonify(error="Cipher shift must be an integer."), 400)

    if not 0 <= shift <= 25:
        return None, (jsonify(error="Cipher shift must be between 0 and 25."), 400)
    return shift, None


def _validate_optional_filename(data: dict[str, Any]) -> Any | None:
    """Reject a non-text filename when a client supplies upload metadata."""
    if "filename" not in data:
        return None

    filename = data["filename"]
    if (
        not isinstance(filename, str)
        or not filename.strip()
        or not filename.strip().lower().endswith(".txt")
    ):
        return jsonify(error="Only .txt files are supported."), 400
    return None


def _remove_optional_text_label(text: str, label: str) -> str:
    """Remove an app-generated text-file label without changing user text."""
    normalized = text.lstrip("\ufeff")
    label_pattern = re.compile(
        rf"^{re.escape(label)}\s*:\s*(?:\r?\n)?",
        re.IGNORECASE,
    )
    return label_pattern.sub("", normalized, count=1)


def _derive_visited_nodes(start: str, astar_result: dict[str, Any]) -> list[str]:
    """Derive stable node order from the existing A* relaxation trace."""
    visited: list[str] = []
    seen: set[str] = set()

    def add(node: str) -> None:
        if node not in seen:
            seen.add(node)
            visited.append(node)

    add(start)
    for edge in astar_result["explored"]:
        add(edge["from"])
        add(edge["to"])
    return visited


def _route_response(astar_result: dict[str, Any], start: str) -> dict[str, Any]:
    """Build the shared, cipher-free map result payload."""
    serialized_route = build_route_message(
        astar_result["path"],
        astar_result["edge_weights"],
        astar_result["total_cost"],
    )
    return {
        "path": astar_result["path"],
        "edge_weights": astar_result["edge_weights"],
        "total_cost": astar_result["total_cost"],
        "serialized_route": serialized_route,
        "start_cost": astar_result["start_cost"],
        "explored": astar_result["explored"],
        "path_edges": astar_result["path_edges"],
        "visited_nodes": _derive_visited_nodes(start, astar_result),
    }


def _unreachable_route_error(start: str, goal: str) -> Any:
    """Return a clear client error when the graph has no start-to-goal route."""
    return jsonify(
        error=f"No route exists between start node {start} and goal node {goal}.",
        start=start,
        goal=goal,
    ), 400


@main.post("/api/astar")
def run_astar():
    """Execute A* and return map/route data without running the cipher."""
    parameters, error = _extract_route_parameters()
    if error:
        return error

    start, goal = parameters
    astar_result = a_star(start, goal)
    if not astar_result["path"]:
        return _unreachable_route_error(start, goal)
    return jsonify(_route_response(astar_result, start))


@main.route("/api/download", methods=["GET", "POST"])
@main.route("/api/export", methods=["GET", "POST"])
def download_route():
    """Recompute and download a labeled plaintext serialized route."""
    parameters, error = _extract_route_parameters()
    if error:
        return error

    start, goal = parameters

    astar_result = a_star(start, goal)
    if not astar_result["path"]:
        return _unreachable_route_error(start, goal)
    serialized_route = build_route_message(
        astar_result["path"],
        astar_result["edge_weights"],
        astar_result["total_cost"],
    )
    filename = f"route_{start}_{goal}.txt"
    file_content = f"Route:\n{serialized_route}"

    return send_file(
        BytesIO(file_content.encode("utf-8")),
        mimetype="text/plain",
        as_attachment=True,
        download_name=filename,
    )


@main.post("/api/encrypt")
def encrypt_route():
    """Validate and encrypt an uploaded plaintext serialized route."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400

    filename_error = _validate_optional_filename(data)
    if filename_error:
        return filename_error

    plaintext = data["plaintext"] if "plaintext" in data else data.get("route")
    if not isinstance(plaintext, str):
        return jsonify(error="Route plaintext must be a string."), 400

    shift, error = _extract_shift(data)
    if error:
        return error

    normalized_plaintext = normalize_labeled_text(plaintext, "Route")
    if not normalized_plaintext:
        return jsonify(error="Route file is empty."), 400

    try:
        parsed_route = parse_route_message(normalized_plaintext)
    except ValueError as err:
        return jsonify(error=f"Invalid route file: {err}"), 400

    ciphertext = caesar_encrypt(normalized_plaintext, shift)
    return jsonify(
        plaintext=normalized_plaintext,
        serialized_route=normalized_plaintext,
        ciphertext=ciphertext,
        path=parsed_route["path"],
        edge_weights=parsed_route["edge_weights"],
        total_cost=parsed_route["total_cost"],
        shift=shift,
        cipher_key=shift,
    )


@main.post("/api/decrypt")
def decrypt_route():
    """Decrypt, validate, and parse an optionally labeled ciphertext route."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400

    filename_error = _validate_optional_filename(data)
    if filename_error:
        return filename_error

    ciphertext = data.get("ciphertext")
    if not isinstance(ciphertext, str):
        return jsonify(error="Ciphertext must be a string."), 400

    shift, error = _extract_shift(data)
    if error:
        return error

    normalized_ciphertext = normalize_labeled_text(ciphertext, "Ciphertext")
    if not normalized_ciphertext:
        return jsonify(error="Ciphertext file is empty."), 400

    decrypted_message = caesar_decrypt(normalized_ciphertext, shift)

    try:
        parsed_route = parse_route_message(decrypted_message)
    except ValueError as err:
        return jsonify(
            error=(
                "Unable to decrypt a valid route with the selected shift: "
                f"{err}"
            )
        ), 400

    return jsonify(
        ciphertext=normalized_ciphertext,
        decrypted_message=decrypted_message,
        plaintext=decrypted_message,
        serialized_route=decrypted_message,
        path=parsed_route["path"],
        edge_weights=parsed_route["edge_weights"],
        total_cost=parsed_route["total_cost"],
        shift=shift,
        cipher_key=shift,
    )


@main.post("/api/encrypt-text")
def encrypt_text_payload():
    """Encrypt user-entered or uploaded text with the existing Caesar cipher."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400

    filename_error = _validate_optional_filename(data)
    if filename_error:
        return filename_error

    plaintext = data.get("plaintext")
    if not isinstance(plaintext, str):
        return jsonify(error="Plaintext must be a string."), 400

    shift, error = _extract_shift(data)
    if error:
        return error

    normalized_plaintext = _remove_optional_text_label(plaintext, "Plaintext")
    if not normalized_plaintext.strip():
        return jsonify(error="Plaintext cannot be empty."), 400

    ciphertext = caesar_encrypt(normalized_plaintext, shift)
    return jsonify(
        plaintext=normalized_plaintext,
        ciphertext=ciphertext,
        shift=shift,
        cipher_key=shift,
    )


@main.post("/api/decrypt-text")
def decrypt_text_payload():
    """Decrypt pasted or uploaded text with the existing Caesar cipher."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400

    filename_error = _validate_optional_filename(data)
    if filename_error:
        return filename_error

    ciphertext = data.get("ciphertext")
    if not isinstance(ciphertext, str):
        return jsonify(error="Ciphertext must be a string."), 400

    shift, error = _extract_shift(data)
    if error:
        return error

    normalized_ciphertext = _remove_optional_text_label(ciphertext, "Ciphertext")
    if not normalized_ciphertext.strip():
        return jsonify(error="Ciphertext cannot be empty."), 400

    decrypted_message = caesar_decrypt(normalized_ciphertext, shift)
    return jsonify(
        ciphertext=normalized_ciphertext,
        decrypted_message=decrypted_message,
        plaintext=decrypted_message,
        shift=shift,
        cipher_key=shift,
    )
