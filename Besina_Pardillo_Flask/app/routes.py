"""Flask web routes for GraphCrypt visualizer, A*, encryption, export, and decryption."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from flask import Blueprint, jsonify, render_template, request, send_file

from .cipher import (
    build_route_message,
    caesar_decrypt,
    caesar_encrypt,
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


def _extract_workflow_parameters() -> tuple[tuple[str, str, int] | None, Any | None]:
    """Validate incoming request parameters for start, goal, and shift."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        # Check query parameters as fallback
        data = request.args.to_dict() if request.args else {}

    if not isinstance(data, dict):
        return None, (jsonify(error="Request body must be a JSON object."), 400)

    start = data.get("start")
    goal = data.get("goal")
    shift = data.get("shift", data.get("cipher_key", 3))

    if not isinstance(start, str) or not isinstance(goal, str):
        return None, (jsonify(error="Both start and goal must be node labels."), 400)

    if start not in LABELS:
        return None, (jsonify(error=f"Invalid start node: {start}", valid_nodes=LABELS), 400)

    if goal not in LABELS:
        return None, (jsonify(error=f"Invalid goal node: {goal}", valid_nodes=LABELS), 400)

    try:
        if isinstance(shift, str) and shift.isdigit():
            shift = int(shift)
        shift = validate_shift(shift)
    except TypeError:
        return None, (jsonify(error="Cipher shift must be an integer."), 400)

    if not (0 <= shift <= 25):
        return None, (jsonify(error="Cipher shift must be between 0 and 25."), 400)

    return (start, goal, shift), None


@main.post("/api/astar")
def run_astar():
    """Execute A* on original graph weights and return route details with single Caesar encryption."""
    parameters, error = _extract_workflow_parameters()
    if error:
        return error

    start, goal, shift = parameters

    # 1. Run pure A* search (cipher has 0 effect)
    astar_result = a_star(start, goal)

    # 2. Serialize final route: PATH|EDGE_WEIGHTS|TOTAL:COST
    serialized_route = build_route_message(
        astar_result["path"],
        astar_result["edge_weights"],
        astar_result["total_cost"],
    )

    # 3. Caesar encrypt serialized route once
    ciphertext = caesar_encrypt(serialized_route, shift)

    # Format response payload
    response_data = {
        "path": astar_result["path"],
        "edge_weights": astar_result["edge_weights"],
        "total_cost": astar_result["total_cost"],
        "serialized_route": serialized_route,
        "ciphertext": ciphertext,
        "shift": shift,
        "cipher_key": shift,
        "start_cost": astar_result["start_cost"],
        "explored": astar_result["explored"],
        "path_edges": astar_result["path_edges"],
    }

    return jsonify(response_data)


@main.route("/api/download", methods=["GET", "POST"])
@main.route("/api/export", methods=["GET", "POST"])
def download_ciphertext():
    """Recompute route, serialize, encrypt once, and download ciphertext-only .txt file."""
    parameters, error = _extract_workflow_parameters()
    if error:
        return error

    start, goal, shift = parameters

    astar_result = a_star(start, goal)
    serialized_route = build_route_message(
        astar_result["path"],
        astar_result["edge_weights"],
        astar_result["total_cost"],
    )
    ciphertext = caesar_encrypt(serialized_route, shift)

    filename = f"route_{start}_{goal}.txt"

    return send_file(
        BytesIO(ciphertext.encode("utf-8")),
        mimetype="text/plain; charset=utf-8",
        as_attachment=True,
        download_name=filename,
    )


@main.post("/api/decrypt")
def decrypt_route():
    """Decrypt a ciphertext route using Caesar Cipher and parse its components."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400

    ciphertext = data.get("ciphertext")
    shift = data.get("shift", data.get("cipher_key", 3))

    if not isinstance(ciphertext, str):
        return jsonify(error="Ciphertext must be a string."), 400

    try:
        if isinstance(shift, str) and shift.isdigit():
            shift = int(shift)
        shift = validate_shift(shift)
    except TypeError:
        return jsonify(error="Cipher shift must be an integer."), 400

    if not (0 <= shift <= 25):
        return jsonify(error="Cipher shift must be between 0 and 25."), 400

    decrypted_message = caesar_decrypt(ciphertext, shift)

    try:
        parsed_route = parse_route_message(decrypted_message)
    except ValueError as err:
        return jsonify(error=f"Failed to parse decrypted route: {err}"), 400

    return jsonify(
        decrypted_message=decrypted_message,
        path=parsed_route["path"],
        edge_weights=parsed_route["edge_weights"],
        total_cost=parsed_route["total_cost"],
        shift=shift,
    )
