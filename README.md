# GraphCrypt: WAYCIPHER Weighted A* + Caesar Cipher

A combined graph-algorithm and cryptography system implementing a clean **WAYCIPHER-style A* + Caesar Cipher** pipeline.

Weighted A* computes the lowest-cost route first on the original graph weights. After the shortest path is found, the route is serialized into `PATH|EDGE_WEIGHTS|TOTAL:COST` and encrypted **once** using a Caesar Cipher. The downloaded `.txt` file contains **only** the encrypted ciphertext, allowing exact round-trip decryption and route parsing.

The Caesar cipher key/shift never influences A*, the shortest path, the original edge weights, or the total cost.

## System Architecture

```text
[Start & Goal Selection]
       │
       ▼
[Weighted A* Search]        (Original weights only; f(n) = g(n) + h(n))
       │
       ▼
[Shortest Path Found]       (A → G → O → P → S → T | Total: 679.9)
       │
       ▼
[Route Serialization]       (A-G-O-P-S-T|195.0,183.5,87.4,124.0,90.0|TOTAL:679.9)
       │
       ▼
[Single Caesar Encrypt]     (D-J-R-S-V-W|428.3,416.8,10.7,457.3,23.3|WRWDO:902.2)
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
[Download route_START_GOAL.txt]   [Caesar Decryption & Parse]
(Contains ciphertext ONLY)        (Recovers original path, weights, and total)
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
- `POST /api/astar`: Runs weighted A* on original weights, serializes route, encrypts once with Caesar cipher, and returns route details.
- `POST /api/download` (and `POST /api/export`): Downloads `route_START_GOAL.txt` containing **only** the ciphertext.
- `POST /api/decrypt`: Decrypts a ciphertext with the given shift and parses the route components back.

## Tests

Run the comprehensive test suite (including 729-pair Dijkstra verification):

```powershell
python -m unittest discover -s tests -v
```
