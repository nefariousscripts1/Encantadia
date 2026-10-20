"""Validated Flask API routes for the text-algorithm laboratory."""

from __future__ import annotations

import base64
import binascii
import tracemalloc
from io import BytesIO
from time import perf_counter_ns

from flask import Blueprint, jsonify, request, send_file

from .text_algorithms import (
    byte_cost,
    huffman_compress,
    huffman_decompress,
    kmp_search,
    knapsack_select,
    randomized_quicksort,
    rank_texts,
)


text_api = Blueprint("text_api", __name__)

MAX_TEXT_BYTES = 1_000_000
MAX_BATCH_BYTES = 2_000_000
MAX_DATASETS = 25


def _json_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify(error="Request body must be a JSON object."), 400)
    return data, None


def _validated_text(data: dict, *, allow_empty: bool = False):
    text = data.get("text")
    if not isinstance(text, str):
        return None, (jsonify(error="Text must be a UTF-8 string."), 400)
    size = len(text.encode("utf-8"))
    if not allow_empty and not text:
        return None, (jsonify(error="Text cannot be empty."), 400)
    if size > MAX_TEXT_BYTES:
        return None, (jsonify(error=f"Text exceeds the {MAX_TEXT_BYTES:,}-byte safety limit."), 413)
    return text, None


def _validated_datasets(data: dict, *, require_text: bool = True):
    datasets = data.get("datasets")
    if not isinstance(datasets, list):
        return None, (jsonify(error="Datasets must be an array."), 400)
    if len(datasets) > MAX_DATASETS:
        return None, (jsonify(error=f"At most {MAX_DATASETS} datasets are allowed."), 400)

    total_bytes = 0
    normalized = []
    for index, dataset in enumerate(datasets):
        if not isinstance(dataset, dict):
            return None, (jsonify(error=f"Dataset {index + 1} must be an object."), 400)
        name = dataset.get("name")
        text = dataset.get("text", "")
        if not isinstance(name, str) or not name.strip():
            return None, (jsonify(error=f"Dataset {index + 1} requires a name."), 400)
        if require_text and not isinstance(text, str):
            return None, (jsonify(error=f"Dataset {name} requires UTF-8 text."), 400)
        if isinstance(text, str):
            total_bytes += len(text.encode("utf-8"))
        normalized.append({**dataset, "name": name.strip(), "text": text})
    if total_bytes > MAX_BATCH_BYTES:
        return None, (jsonify(error=f"Dataset batch exceeds the {MAX_BATCH_BYTES:,}-byte safety limit."), 413)
    return normalized, None


@text_api.post("/api/text/kmp")
def run_kmp():
    data, error = _json_object()
    if error:
        return error
    text, error = _validated_text(data, allow_empty=True)
    if error:
        return error
    pattern = data.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        return jsonify(error="Search pattern cannot be empty."), 400
    if len(pattern.encode("utf-8")) > 10_000:
        return jsonify(error="Search pattern exceeds the 10,000-byte safety limit."), 413
    result = kmp_search(text, pattern)
    return jsonify(
        **result,
        text_length=len(text),
        pattern_length=len(pattern),
        time_complexity="O(n + m)",
        space_complexity="O(m), excluding output",
    )


def _huffman_json(result: dict, *, include_data: bool = True) -> dict:
    frequency_rows = []
    for symbol in sorted(result["frequencies"]):
        label = chr(symbol) if 32 <= symbol <= 126 else f"0x{symbol:02X}"
        frequency_rows.append(
            {
                "byte": symbol,
                "symbol": label,
                "frequency": result["frequencies"][symbol],
                "code": result["codes"][symbol],
            }
        )
    response = {
        key: value
        for key, value in result.items()
        if key not in {"data", "frequencies", "codes"}
    }
    response.update(
        frequency_table=frequency_rows,
        time_complexity="O(n + k log k)",
        space_complexity="O(k + n) including output",
    )
    if include_data:
        response["data_base64"] = base64.b64encode(result["data"]).decode("ascii")
    return response


@text_api.post("/api/text/huffman/compress")
def compress_huffman():
    data, error = _json_object()
    if error:
        return error
    text, error = _validated_text(data, allow_empty=True)
    if error:
        return error
    result = huffman_compress(text)
    decoded = huffman_decompress(result["data"])
    response = _huffman_json(result)
    response.update(
        decompression_time_ms=decoded["execution_time_ms"],
        verified=decoded["text"] == text,
    )
    return jsonify(response)


@text_api.post("/api/text/huffman/decompress")
def decompress_huffman():
    data, error = _json_object()
    if error:
        return error
    encoded = data.get("data_base64")
    if not isinstance(encoded, str):
        return jsonify(error="data_base64 must be a string."), 400
    try:
        compressed = base64.b64decode(encoded, validate=True)
        result = huffman_decompress(compressed)
    except (binascii.Error, ValueError) as decode_error:
        return jsonify(error=str(decode_error)), 400
    return jsonify(**result, verified_utf8=True)


@text_api.post("/api/text/huffman/download")
def download_huffman():
    data, error = _json_object()
    if error:
        return error
    text, error = _validated_text(data, allow_empty=True)
    if error:
        return error
    result = huffman_compress(text)
    return send_file(
        BytesIO(result["data"]),
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name="graphcrypt_huffman.gch",
    )


@text_api.post("/api/text/knapsack")
def optimize_datasets():
    data, error = _json_object()
    if error:
        return error
    datasets, error = _validated_datasets(data, require_text=False)
    if error:
        return error
    try:
        items = []
        for dataset in datasets:
            byte_size = dataset.get("byte_size")
            if byte_size is None and isinstance(dataset.get("text"), str):
                byte_size = len(dataset["text"].encode("utf-8"))
            derived_cost = byte_cost(byte_size or 0)
            items.append(
                {
                    "name": dataset["name"],
                    "byte_size": byte_size,
                    "cost": dataset.get("cost", derived_cost),
                    "priority": dataset.get("priority", 0),
                }
            )
        result = knapsack_select(items, data.get("budget"))
    except (TypeError, ValueError) as algorithm_error:
        return jsonify(error=str(algorithm_error)), 400
    return jsonify(
        **result,
        cost_unit="1 unit = 1 KiB (1,024 bytes), rounded up for non-empty files",
        time_complexity="O(N × B)",
        space_complexity="O(B) scores and selection masks",
    )


@text_api.post("/api/text/rank")
def rank_search_results():
    data, error = _json_object()
    if error:
        return error
    datasets, error = _validated_datasets(data)
    if error:
        return error
    try:
        result = rank_texts(datasets, data.get("pattern"), data.get("seed"))
    except (TypeError, ValueError) as algorithm_error:
        return jsonify(error=str(algorithm_error)), 400
    return jsonify(
        **result,
        average_time_complexity="O(N log N)",
        worst_time_complexity="O(N²)",
        average_space_complexity="O(log N)",
        worst_space_complexity="O(N)",
    )


def _measure(name: str, input_size: int, complexity: str, space: str, operation):
    tracemalloc.start()
    started = perf_counter_ns()
    status = "Completed"
    result_summary = ""
    try:
        result_summary = operation()
    except Exception as error:  # report benchmark failure instead of hiding it
        status = f"Failed: {error}"
    elapsed_ms = round((perf_counter_ns() - started) / 1_000_000, 6)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "algorithm": name,
        "input_size": input_size,
        "execution_time_ms": elapsed_ms,
        "time_complexity": complexity,
        "space_complexity": space,
        "measured_memory_bytes": peak_bytes,
        "memory_method": "Python allocation peak (tracemalloc)",
        "status": status,
        "result": result_summary,
    }


@text_api.post("/api/text/benchmark")
def benchmark_algorithms():
    data, error = _json_object()
    if error:
        return error
    sizes = data.get("sizes", [1_000, 10_000, 50_000])
    if (
        not isinstance(sizes, list)
        or not sizes
        or len(sizes) > 5
        or any(isinstance(size, bool) or not isinstance(size, int) or size < 10 or size > 100_000 for size in sizes)
    ):
        return jsonify(error="Provide 1–5 integer sizes from 10 to 100,000."), 400

    rows = []
    for size in sizes:
        sample = ("algorithm analysis data " * ((size // 24) + 1))[:size]
        category = "Small" if size <= 2_000 else "Medium" if size <= 20_000 else "Large"
        item_count = max(1, min(80, size // 500))
        items = [
            {"name": f"dataset-{index + 1}", "cost": (index % 9) + 1, "priority": (index * 7) % 23}
            for index in range(item_count)
        ]
        budget = min(500, max(10, item_count * 3))
        sort_count = max(10, min(5_000, size // 10))
        rankings = [
            {"name": f"file-{index:05d}.txt", "match_count": (index * 37) % 101}
            for index in range(sort_count)
        ]
        measurements = (
            _measure("KMP String Matching", size, "O(n + m)", "O(m), excluding output", lambda sample=sample: f'{kmp_search(sample, "data")["match_count"]} matches'),
            _measure("Huffman Coding", size, "O(n + k log k)", "O(k + n) including output", lambda sample=sample: f'{huffman_compress(sample)["compressed_size_bytes"]} bytes'),
            _measure("0/1 Knapsack", item_count, "O(N × B)", "O(B)", lambda items=items, budget=budget: f'{len(knapsack_select(items, budget)["selected_items"])} selected'),
            _measure("Randomized QuickSort", sort_count, "Average O(N log N); worst O(N²)", "Average O(log N); worst O(N)", lambda rankings=rankings: f'{len(randomized_quicksort(rankings, 42)["ranked_results"])} ranked'),
        )
        for row in measurements:
            row["dataset_category"] = category
            rows.append(row)

    return jsonify(
        rows=rows,
        sizes=sizes,
        timing_method="time.perf_counter_ns; excludes request transfer and browser rendering",
        memory_note="Peak Python allocations measured with tracemalloc; native/runtime overhead is not included.",
    )
