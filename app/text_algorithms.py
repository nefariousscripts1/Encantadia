"""Educational text algorithms used by the Algorithm Analysis workspace.

The implementations in this module intentionally avoid Python's built-in
search, sort, and compression helpers so the project can expose and test the
actual algorithms.
"""

from __future__ import annotations

import heapq
import math
import random
import struct
from dataclasses import dataclass
from time import perf_counter_ns
from typing import Any, Iterable


HUFFMAN_MAGIC = b"GCHF"
HUFFMAN_VERSION = 1
HUFFMAN_FIXED_HEADER = struct.Struct(">4sBQHB")
HUFFMAN_FREQUENCY_ENTRY = struct.Struct(">BQ")
MAX_KNAPSACK_CELLS = 2_000_000
MAX_KNAPSACK_BUDGET = 100_000


def _elapsed_ms(start_ns: int) -> float:
    return round((perf_counter_ns() - start_ns) / 1_000_000, 6)


def build_lps(pattern: str) -> list[int]:
    """Build the KMP longest-proper-prefix/suffix table in O(m) time."""

    if not isinstance(pattern, str):
        raise TypeError("Pattern must be a string.")

    lps = [0] * len(pattern)
    prefix_length = 0
    index = 1
    while index < len(pattern):
        if pattern[index] == pattern[prefix_length]:
            prefix_length += 1
            lps[index] = prefix_length
            index += 1
        elif prefix_length:
            prefix_length = lps[prefix_length - 1]
        else:
            index += 1
    return lps


def kmp_search(text: str, pattern: str) -> dict[str, Any]:
    """Return every zero-based match, including overlapping matches."""

    if not isinstance(text, str) or not isinstance(pattern, str):
        raise TypeError("Text and pattern must be strings.")

    started = perf_counter_ns()
    if not pattern:
        return {
            "matches": [],
            "match_count": 0,
            "lps": [],
            "execution_time_ms": _elapsed_ms(started),
        }

    lps = build_lps(pattern)
    matches: list[int] = []
    text_index = 0
    pattern_index = 0

    while text_index < len(text):
        if text[text_index] == pattern[pattern_index]:
            text_index += 1
            pattern_index += 1
            if pattern_index == len(pattern):
                matches.append(text_index - pattern_index)
                pattern_index = lps[pattern_index - 1]
        elif pattern_index:
            pattern_index = lps[pattern_index - 1]
        else:
            text_index += 1

    return {
        "matches": matches,
        "match_count": len(matches),
        "lps": lps,
        "execution_time_ms": _elapsed_ms(started),
    }


@dataclass(order=True)
class _HuffmanHeapItem:
    frequency: int
    minimum_symbol: int
    sequence: int
    node: Any


@dataclass
class _HuffmanNode:
    symbol: int | None = None
    left: "_HuffmanNode | None" = None
    right: "_HuffmanNode | None" = None


def _byte_frequencies(data: bytes) -> dict[int, int]:
    frequencies: dict[int, int] = {}
    for symbol in data:
        frequencies[symbol] = frequencies.get(symbol, 0) + 1
    return frequencies


def _build_huffman_tree(frequencies: dict[int, int]) -> _HuffmanNode | None:
    heap: list[_HuffmanHeapItem] = []
    sequence = 0
    for symbol in range(256):
        if symbol in frequencies:
            node = _HuffmanNode(symbol=symbol)
            heapq.heappush(
                heap,
                _HuffmanHeapItem(frequencies[symbol], symbol, sequence, node),
            )
            sequence += 1

    if not heap:
        return None

    while len(heap) > 1:
        first = heapq.heappop(heap)
        second = heapq.heappop(heap)
        parent = _HuffmanNode(left=first.node, right=second.node)
        heapq.heappush(
            heap,
            _HuffmanHeapItem(
                first.frequency + second.frequency,
                min(first.minimum_symbol, second.minimum_symbol),
                sequence,
                parent,
            ),
        )
        sequence += 1
    return heap[0].node


def _build_huffman_codes(root: _HuffmanNode | None) -> dict[int, str]:
    codes: dict[int, str] = {}
    if root is None:
        return codes

    stack = [(root, "")]
    while stack:
        node, prefix = stack.pop()
        if node.symbol is not None:
            codes[node.symbol] = prefix or "0"
            continue
        if node.right is not None:
            stack.append((node.right, prefix + "1"))
        if node.left is not None:
            stack.append((node.left, prefix + "0"))
    return codes


def _pack_codes(data: bytes, codes: dict[int, str]) -> tuple[bytes, int, int]:
    payload = bytearray()
    current_byte = 0
    bits_in_byte = 0
    bit_count = 0

    for symbol in data:
        for bit in codes[symbol]:
            current_byte = (current_byte << 1) | (bit == "1")
            bits_in_byte += 1
            bit_count += 1
            if bits_in_byte == 8:
                payload.append(current_byte)
                current_byte = 0
                bits_in_byte = 0

    padding_bits = (8 - bits_in_byte) % 8
    if bits_in_byte:
        payload.append(current_byte << padding_bits)
    return bytes(payload), padding_bits, bit_count


def _huffman_header(
    original_size: int, frequencies: dict[int, int], padding_bits: int
) -> bytes:
    header = bytearray(
        HUFFMAN_FIXED_HEADER.pack(
            HUFFMAN_MAGIC,
            HUFFMAN_VERSION,
            original_size,
            len(frequencies),
            padding_bits,
        )
    )
    for symbol in sorted(frequencies):
        header.extend(HUFFMAN_FREQUENCY_ENTRY.pack(symbol, frequencies[symbol]))
    return bytes(header)


def huffman_compress(text: str) -> dict[str, Any]:
    """Compress UTF-8 bytes into the deterministic GraphCrypt Huffman format."""

    if not isinstance(text, str):
        raise TypeError("Text must be a string.")

    started = perf_counter_ns()
    original = text.encode("utf-8")
    frequencies = _byte_frequencies(original)
    tree = _build_huffman_tree(frequencies)
    codes = _build_huffman_codes(tree)
    payload, padding_bits, bit_count = _pack_codes(original, codes)
    header = _huffman_header(len(original), frequencies, padding_bits)
    compressed = header + payload
    elapsed = _elapsed_ms(started)

    original_size = len(original)
    compressed_size = len(compressed)
    ratio = original_size / compressed_size if compressed_size else None
    savings = (
        ((original_size - compressed_size) / original_size) * 100
        if original_size
        else 0.0
    )

    return {
        "data": compressed,
        "original_size_bytes": original_size,
        "payload_size_bytes": len(payload),
        "metadata_size_bytes": len(header),
        "compressed_size_bytes": compressed_size,
        "encoded_bits": bit_count,
        "padding_bits": padding_bits,
        "compression_ratio": round(ratio, 6) if ratio is not None else None,
        "space_savings_percent": round(savings, 3),
        "frequencies": frequencies,
        "codes": codes,
        "execution_time_ms": elapsed,
    }


def _parse_huffman_header(data: bytes) -> tuple[int, dict[int, int], int, int]:
    if len(data) < HUFFMAN_FIXED_HEADER.size:
        raise ValueError("Compressed data is too short to contain a valid header.")

    magic, version, original_size, symbol_count, padding_bits = (
        HUFFMAN_FIXED_HEADER.unpack_from(data)
    )
    if magic != HUFFMAN_MAGIC or version != HUFFMAN_VERSION:
        raise ValueError("Unsupported or invalid Huffman file format.")
    if symbol_count > 256 or padding_bits > 7:
        raise ValueError("Huffman header contains invalid metadata.")

    offset = HUFFMAN_FIXED_HEADER.size
    expected_header_size = offset + symbol_count * HUFFMAN_FREQUENCY_ENTRY.size
    if len(data) < expected_header_size:
        raise ValueError("Compressed Huffman metadata is incomplete.")

    frequencies: dict[int, int] = {}
    for _ in range(symbol_count):
        symbol, frequency = HUFFMAN_FREQUENCY_ENTRY.unpack_from(data, offset)
        offset += HUFFMAN_FREQUENCY_ENTRY.size
        if symbol in frequencies or frequency <= 0:
            raise ValueError("Huffman header contains an invalid frequency table.")
        frequencies[symbol] = frequency

    if sum(frequencies.values()) != original_size:
        raise ValueError("Huffman frequency totals do not match the original size.")
    if original_size == 0 and frequencies:
        raise ValueError("Empty Huffman content cannot declare symbols.")
    if original_size and not frequencies:
        raise ValueError("Non-empty Huffman content requires a frequency table.")
    return original_size, frequencies, padding_bits, offset


def huffman_decompress(data: bytes) -> dict[str, Any]:
    """Decode GraphCrypt Huffman bytes and return their exact UTF-8 text."""

    if not isinstance(data, bytes):
        raise TypeError("Compressed data must be bytes.")

    started = perf_counter_ns()
    original_size, frequencies, padding_bits, payload_offset = _parse_huffman_header(data)
    payload = data[payload_offset:]
    if not original_size:
        if payload:
            raise ValueError("Empty Huffman content must not contain a payload.")
        return {"text": "", "execution_time_ms": _elapsed_ms(started)}
    if not payload:
        raise ValueError("Compressed Huffman payload is missing.")

    tree = _build_huffman_tree(frequencies)
    if tree is None:
        raise ValueError("Unable to reconstruct the Huffman tree.")
    codes = _build_huffman_codes(tree)
    expected_bits = sum(
        frequency * len(codes[symbol])
        for symbol, frequency in frequencies.items()
    )
    expected_payload_size = math.ceil(expected_bits / 8)
    expected_padding = (8 - expected_bits % 8) % 8
    if len(payload) != expected_payload_size or padding_bits != expected_padding:
        raise ValueError("Compressed Huffman payload length or padding is invalid.")

    if tree.symbol is not None:
        decoded = bytes([tree.symbol]) * original_size
    else:
        decoded_bytes = bytearray()
        node = tree
        total_bits = len(payload) * 8 - padding_bits
        for bit_index in range(total_bits):
            byte_value = payload[bit_index // 8]
            bit = (byte_value >> (7 - bit_index % 8)) & 1
            node = node.right if bit else node.left
            if node is None:
                raise ValueError("Compressed Huffman payload is corrupt.")
            if node.symbol is not None:
                decoded_bytes.append(node.symbol)
                node = tree
                if len(decoded_bytes) == original_size:
                    break
        if len(decoded_bytes) != original_size or node is not tree:
            raise ValueError("Compressed Huffman payload ended unexpectedly.")
        decoded = bytes(decoded_bytes)

    try:
        text = decoded.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Decompressed content is not valid UTF-8 text.") from error
    return {"text": text, "execution_time_ms": _elapsed_ms(started)}


def byte_cost(byte_size: int) -> int:
    """Convert bytes to whole KiB processing units (minimum one if non-empty)."""

    if isinstance(byte_size, bool) or not isinstance(byte_size, int) or byte_size < 0:
        raise ValueError("Byte size must be a non-negative integer.")
    return math.ceil(byte_size / 1024) if byte_size else 0


def knapsack_select(items: Iterable[dict[str, Any]], budget: int) -> dict[str, Any]:
    """Select each item at most once using memory-optimized 0/1 DP."""

    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ValueError("Budget must be a non-negative integer.")
    if budget > MAX_KNAPSACK_BUDGET:
        raise ValueError(f"Budget exceeds the {MAX_KNAPSACK_BUDGET:,}-unit safety limit.")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("Every knapsack item must be an object.")
        name = item.get("name")
        priority = item.get("priority", 0)
        cost = item.get("cost")
        if cost is None:
            cost = byte_cost(item.get("byte_size", 0))
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Item {index + 1} requires a name.")
        if isinstance(cost, bool) or not isinstance(cost, int) or cost < 0:
            raise ValueError(f"Item {name} has an invalid cost.")
        if isinstance(priority, bool) or not isinstance(priority, (int, float)):
            raise ValueError(f"Item {name} has an invalid priority.")
        if not math.isfinite(priority) or priority < 0:
            raise ValueError(f"Item {name} priority must be finite and non-negative.")
        normalized.append({**item, "name": name, "cost": cost, "priority": priority})

    started = perf_counter_ns()
    if not normalized:
        return {
            "selected_items": [],
            "total_cost": 0,
            "budget": budget,
            "total_score": 0.0,
            "execution_time_ms": _elapsed_ms(started),
        }

    if len(normalized) * (budget + 1) > MAX_KNAPSACK_CELLS:
        raise ValueError(
            f"Knapsack request exceeds the {MAX_KNAPSACK_CELLS:,}-cell safety limit."
        )

    best_scores = [0.0] * (budget + 1)
    selected_masks = [0] * (budget + 1)

    for index, item in enumerate(normalized):
        cost = item["cost"]
        value = float(item["priority"])
        for capacity in range(budget, cost - 1, -1):
            candidate = best_scores[capacity - cost] + value
            if candidate > best_scores[capacity]:
                best_scores[capacity] = candidate
                selected_masks[capacity] = selected_masks[capacity - cost] | (1 << index)

    mask = selected_masks[budget]
    selected = [item for index, item in enumerate(normalized) if mask & (1 << index)]
    total_cost = sum(item["cost"] for item in selected)
    return {
        "selected_items": selected,
        "total_cost": total_cost,
        "budget": budget,
        "total_score": round(sum(float(item["priority"]) for item in selected), 6),
        "execution_time_ms": _elapsed_ms(started),
    }


def randomized_quicksort(
    results: Iterable[dict[str, Any]], seed: int | None = None
) -> dict[str, Any]:
    """Rank search results by descending count using randomized three-way quicksort."""

    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ValueError("Random seed must be an integer or null.")

    values: list[dict[str, Any]] = []
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            raise ValueError("Every ranking result must be an object.")
        name = result.get("name")
        match_count = result.get("match_count")
        if not isinstance(name, str) or not name:
            raise ValueError("Every ranking result requires a file name.")
        if (
            isinstance(match_count, bool)
            or not isinstance(match_count, int)
            or match_count < 0
        ):
            raise ValueError(f"Result {name} has an invalid match count.")
        values.append({**result, "_original_index": index})

    randomizer = random.Random(seed)
    started = perf_counter_ns()

    def rank_key(value: dict[str, Any]) -> tuple[Any, ...]:
        return (-value["match_count"], value["name"].casefold(), value["name"], value["_original_index"])

    def quicksort(low: int, high: int) -> None:
        if low >= high:
            return
        pivot = rank_key(values[randomizer.randint(low, high)])
        lower = low
        scan = low
        upper = high
        while scan <= upper:
            key = rank_key(values[scan])
            if key < pivot:
                values[lower], values[scan] = values[scan], values[lower]
                lower += 1
                scan += 1
            elif key > pivot:
                values[scan], values[upper] = values[upper], values[scan]
                upper -= 1
            else:
                scan += 1
        quicksort(low, lower - 1)
        quicksort(upper + 1, high)

    quicksort(0, len(values) - 1)
    elapsed = _elapsed_ms(started)
    for value in values:
        value.pop("_original_index", None)
    return {"ranked_results": values, "execution_time_ms": elapsed, "seed": seed}


def rank_texts(
    datasets: Iterable[dict[str, Any]], pattern: str, seed: int | None = None
) -> dict[str, Any]:
    """Run KMP over each dataset, then rank the files with randomized quicksort."""

    if not isinstance(pattern, str) or not pattern:
        raise ValueError("Search pattern cannot be empty.")
    search_results = []
    kmp_time = 0.0
    for dataset in datasets:
        if not isinstance(dataset, dict):
            raise ValueError("Every dataset must be an object.")
        name = dataset.get("name")
        text = dataset.get("text")
        if not isinstance(name, str) or not name or not isinstance(text, str):
            raise ValueError("Every dataset requires a name and text.")
        result = kmp_search(text, pattern)
        kmp_time += result["execution_time_ms"]
        search_results.append(
            {"name": name, "match_count": result["match_count"], "matches": result["matches"]}
        )
    ranked = randomized_quicksort(search_results, seed)
    ranked["kmp_execution_time_ms"] = round(kmp_time, 6)
    return ranked
