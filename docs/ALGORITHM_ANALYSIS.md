# Algorithm Analysis and Text Processing

## Purpose and integration

GraphCrypt remains a Flask and vanilla-JavaScript application. The original
weighted A* and Caesar Cipher workflow is unchanged. The **Algorithm Analysis**
workspace uses an in-browser dataset collection so the same selected UTF-8 text
can be searched, compressed, optimized, and ranked without introducing a
database. CPU work and trusted file generation run through Flask APIs.

The standalone implementations live in `app/text_algorithms.py`; request
validation and JSON/download endpoints live in `app/text_routes.py`; the interface
is in `app/templates/index.html`, `app/static/js/text-lab.js`, and
`app/static/css/style.css`.

## KMP string matching

KMP first constructs a Longest Prefix Suffix (LPS) table for the pattern. When
a comparison fails, the table determines the next pattern position, so the
source-text index never moves backward. The implementation returns every
zero-based starting position and resets through the LPS table after a complete
match, which preserves overlapping matches such as `aaa` in `aaaaa`.

- Time: `O(n + m)`
- Auxiliary space: `O(m)`, excluding returned match positions
- Edge cases: empty source text produces no matches; the API rejects an empty
  pattern with a clear validation error; repeated, overlapping, and missing
  patterns are tested.

## Huffman coding

Huffman operates on UTF-8 bytes, not Python Unicode code points. This makes the
encoded symbol alphabet unambiguous and guarantees that arbitrary valid UTF-8
text round-trips exactly. A deterministic heap constructs the tree, the tree
generates prefix-free codes, and the encoder packs individual bits into bytes.
The `.gch` format is not a textual sequence of `0` and `1` characters.

### Binary `.gch` format

All multibyte integers use big-endian byte order.

| Field | Size | Meaning |
| --- | ---: | --- |
| Magic | 4 bytes | ASCII `GCHF` |
| Version | 1 byte | Currently `1` |
| Original size | 8 bytes | Original UTF-8 byte count |
| Symbol count | 2 bytes | Number of frequency entries |
| Padding count | 1 byte | Unused low bits in the final payload byte |
| Frequency entries | 9 bytes each | One byte symbol plus an 8-byte frequency |
| Encoded payload | Variable | Packed Huffman bits |

The decoder rebuilds the same deterministic tree from the stored frequencies.
Metrics distinguish encoded payload bytes from metadata and total file bytes.

- Construction time: `O(n + k log k)`, where `k ≤ 256`
- Space: `O(k + n)` including encoded output
- Compression ratio: `original bytes / total compressed bytes`
- Space savings: `((original bytes - total compressed bytes) / original bytes) × 100`

For an empty source, the ratio and savings are reported as `0` rather than
dividing by zero. A one-symbol source receives code `0`. Small inputs may have
negative savings because a lossless, self-describing file must include metadata;
the interface reports that result rather than hiding it.

## 0/1 Knapsack optimization

Each dataset receives an integer processing cost of one unit per started KiB
(`ceil(UTF-8 bytes / 1024)`); an empty dataset costs zero units. Users assign a
non-negative priority and set the total budget. A descending-capacity dynamic
programming pass ensures every dataset can be selected at most once. Selection
is reconstructed from integer bit masks, so the implementation stores one row
of score states rather than a full `N × B` matrix.

- Time: `O(N × B)`
- DP score space: `O(B)`; selection masks are stored beside those states
- Safety: requests above 2,000,000 `N × (B + 1)` cells are rejected before the
  DP begins.
- Reproducibility: equal inputs retain deterministic input-order tie behavior.

## Randomized QuickSort ranking

Batch ranking first runs KMP on every dataset. Randomized QuickSort then chooses
pivots using a local pseudorandom generator and performs three-way partitioning.
Files rank by descending match count, then case-insensitive name, exact name,
and original position. Those tie rules keep the final order deterministic even
when pivot choices differ. An optional integer seed reproduces the same pivot
sequence for testing.

- Average time: `O(N log N)`
- Worst-case time: `O(N²)`
- Average recursive space: `O(log N)`
- Worst-case recursive space: `O(N)`

## Performance analysis

The Performance panel generates small, medium, and large samples using sizes
configured by the user. Timing uses Python's monotonic `time.perf_counter_ns`
around algorithm execution only; request transfer and browser rendering are
excluded. Peak memory is measured with `tracemalloc` and is explicitly labeled
as traced Python allocations because it does not represent every byte held by
the interpreter or native runtime.

Theoretical complexity describes how resource requirements grow with input.
Measured performance is an observation from one machine and one data
distribution; interpreter overhead, cache behavior, symbol frequencies, pivot
choices, and competing system work can all affect it. The application therefore
does not ship hardcoded timing or memory claims.

Default categories are:

- Small: up to 2,000 source characters
- Medium: 2,001–20,000 source characters
- Large: above 20,000 source characters (bounded at 100,000 per benchmark)

## Reproducible evaluation

From PowerShell in the project directory:

```powershell
.\venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
python run.py
```

Open `http://127.0.0.1:5000`, choose **Algorithm Analysis**, and use **Load
Sample**. Suggested checks:

1. Search for `algorithm` and inspect all positions, highlights, and the LPS table.
2. Compress the sample, confirm exact verification, compare payload and total
   `.gch` sizes, download the file, and run **Decompress Again**.
3. Add or upload more `.txt` datasets, assign priorities, and change the KiB
   budget to verify 0/1 selection boundaries.
4. Search all datasets with seed `42` and repeat the ranking.
5. Run sizes `1000, 10000, 50000` in Performance and compare the table and chart.

Automated tests cover algorithm correctness, overlapping KMP matches, UTF-8 and
randomized Huffman round trips, size calculations, Knapsack edge cases,
QuickSort ties and reproducibility, APIs, and the original A* plus Caesar flow.
