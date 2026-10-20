# GraphCrypt: Weighted A* Map + Caesar Cipher Workspace

GraphCrypt keeps route planning separate from route-file processing while preserving the existing weighted A* search, serialization format, and Caesar implementation.

The **Map** page computes the shortest path using the original graph weights, shows the explored search trace, applies the selected Caesar shift to the serialized route, and downloads an encrypted `.txt` file. The **Cipher** page has independent Encrypt and Decrypt sections for `.txt` route files. File encryption and decryption run only after the corresponding action button is pressed, and the shift key never influences A* or the route cost.

The integrated **Algorithms** page adds a shared UTF-8 dataset workspace with manually implemented KMP pattern matching, byte-packed Huffman compression, memory-optimized 0/1 Knapsack selection, Randomized QuickSort ranking, and measured performance analysis. See [`docs/ALGORITHM_ANALYSIS.md`](docs/ALGORITHM_ANALYSIS.md) for the binary format, complexity analysis, safety limits, and reproducible evaluation procedure.

## System Architecture

```text
[Map: Start & Goal Selection]
       │
       ▼
[Weighted A* Search]        (Original weights; f(n) = g(n) + h(n))
       │
       ▼
[Route Serialization]       (A-G-O-P-S-T|195.0,183.5,87.4,124.0,90.0|TOTAL:679.9)
       │
       ▼
[Caesar Shift 0–25]         (Applied after A* resolves the route)
       │
       ▼
[Download encrypted Route .txt]
       │
       ▼
[Cipher: Decrypt]           (explicit action + same shift)
       │
       ▼
[Restored route, weights, and total distance]
```

## Windows PowerShell setup

Open PowerShell in this project directory:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Open in a browser: `http://127.0.0.1:5000`

## API Endpoints

- `GET /`: Displays the GraphCrypt interactive visualizer.
- `GET /api/graph`: Returns graph nodes, coordinates, weighted edges, and canvas dimensions.
- `POST /api/astar`: Runs weighted A* on original weights and returns path, edge weights, total distance, visited nodes, search trace, and `serialized_route`. It does not run the cipher; the Map page sends the completed route to `/api/encrypt` using the selected shift.
- `POST /api/download` (and `POST /api/export`): Downloads `route_START_GOAL.txt` containing `Route:` followed by the plaintext serialized route.
- `POST /api/encrypt`: Accepts `{plaintext, shift}` (or the legacy `route` alias), validates the route, and returns the encrypted payload plus parsed route details. Shifts are restricted to `0–25`.
- `POST /api/decrypt`: Accepts `{ciphertext, shift}`, optionally strips a leading `Ciphertext:` label, decrypts, validates, and returns the restored route details.

The serialized route format is:

```text
PATH|EDGE_WEIGHTS|TOTAL:COST
```

For example, an encrypted download may contain:

```text
Ciphertext:
D-J-R-S-V-W|428.3,416.8,10.7,457.3,23.3|WRWDO:902.2
```

## Tests

Run the comprehensive test suite (including 729-pair Dijkstra verification):

```powershell
python -m unittest discover -s tests -v
```
