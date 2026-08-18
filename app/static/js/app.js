"use strict";

/**
 * GraphCrypt Flat Design Color Tokens
 */
const COLORS = {
    fallback: "#F8FAFC",
    fallbackGrid: "rgba(203, 213, 225, 0.4)",
    edge: "#94A3B8",
    node: "#FFFFFF",
    nodeBorder: "#2563EB",
    nodeText: "#1E293B",
    explored: "#8B5CF6",
    start: "#16A34A",
    goal: "#DC2626",
    path: "#2563EB",
    white: "#FFFFFF",
    dark: "#0F172A",
    distanceBackground: "#FFFFFF",
    distanceBorder: "#CBD5E1",
    distanceText: "#0F172A",
};

const STEPS = 14;
const STEP_DELAY = 2;
const EDGE_PAUSE = 20;
const DEBUG_COORDINATES = new URLSearchParams(window.location.search).get("debugCoordinates") === "1";

// DOM Elements
const canvas = document.querySelector("#graphCanvas");
const context = canvas.getContext("2d");
const startSelect = document.querySelector("#startNode");
const goalSelect = document.querySelector("#goalNode");
const cipherKeyInput = document.querySelector("#cipherKey");
const cipherKeyValue = document.querySelector("#cipherKeyValue");
const runButton = document.querySelector("#runButton");
const resetButton = document.querySelector("#resetButton");
const showDistanceButton = document.querySelector("#showDistanceButton");
const hideDistanceButton = document.querySelector("#hideDistanceButton");
const downloadButton = document.querySelector("#downloadButton");
const copyCiphertextButton = document.querySelector("#copyCiphertextButton");
const algorithmLog = document.querySelector("#algorithmLog");
const encryptedExport = document.querySelector("#encryptedExport");
const decryptedVerificationBox = document.querySelector("#decryptedVerificationBox");
const encryptionStatus = document.querySelector("#encryptionStatus");
const cryptoActiveShift = document.querySelector("#cryptoActiveShift");
const runStatus = document.querySelector("#runStatus");
const mapStatus = document.querySelector("#mapStatus");

// Result card elements
const routeResultStatusBadge = document.querySelector("#routeResultStatusBadge");
const routeMetricDistance = document.querySelector("#routeMetricDistance");
const routeMetricNodes = document.querySelector("#routeMetricNodes");
const routeMetricStatus = document.querySelector("#routeMetricStatus");
const routeSequenceDisplay = document.querySelector("#routeSequenceDisplay");

// Tab controls for computation log
const tabTableView = document.querySelector("#tabTableView");
const tabRawLogView = document.querySelector("#tabRawLogView");
const tableViewContainer = document.querySelector("#tableViewContainer");
const rawLogViewContainer = document.querySelector("#rawLogViewContainer");
const computationTableBody = document.querySelector("#computationTableBody");

// State
let graph = null;
let mapLoaded = false;
let showWeights = false;
let animationToken = 0;
let logSequence = 0;
let stepCounter = 0;
let currentResult = null;
let currentRequest = null;
let completedExploredEdges = [];
let completedPathEdges = [];
let exploredNodes = new Set();
let finalPathNodes = new Set();
let activeSegment = null;

// Map image loading
const mapImage = new Image();
mapImage.src = "/static/images/argentina_map.png";
mapImage.addEventListener("load", () => {
    mapLoaded = true;
    if (mapStatus) {
        mapStatus.textContent = "● Map Online";
        mapStatus.className = "badge badge-success";
    }
    drawScene();
});
mapImage.addEventListener("error", () => {
    mapLoaded = false;
    if (mapStatus) {
        mapStatus.textContent = "Fallback Grid";
        mapStatus.className = "badge badge-neutral";
    }
    drawScene();
});

function delay(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function coordinates(label) {
    return graph.coordinates[label];
}

function drawingScale() {
    return canvas.width / 700;
}

function setBusy(isBusy) {
    runButton.disabled = isBusy;
    startSelect.disabled = isBusy;
    goalSelect.disabled = isBusy;
    cipherKeyInput.disabled = isBusy;
}

function drawFallbackBackground() {
    context.fillStyle = COLORS.fallback;
    context.fillRect(0, 0, canvas.width, canvas.height);

    const scale = drawingScale();
    context.strokeStyle = COLORS.fallbackGrid;
    context.lineWidth = scale;
    for (let x = 20 * scale; x < canvas.width; x += 40 * scale) {
        context.beginPath();
        context.moveTo(x, 0);
        context.lineTo(x, canvas.height);
        context.stroke();
    }
    for (let y = 20 * scale; y < canvas.height; y += 40 * scale) {
        context.beginPath();
        context.moveTo(0, y);
        context.lineTo(canvas.width, y);
        context.stroke();
    }
}

function drawEdge(edge, color, width, progress = 1) {
    const [x1, y1] = coordinates(edge.from);
    const [x2, y2] = coordinates(edge.to);
    const endX = x1 + (x2 - x1) * progress;
    const endY = y1 + (y2 - y1) * progress;

    context.beginPath();
    context.moveTo(x1, y1);
    context.lineTo(endX, endY);
    context.strokeStyle = color;
    context.lineWidth = width * drawingScale();
    context.lineCap = "round";
    context.stroke();
}

function nodeColor(label) {
    if (label === startSelect.value) {
        return COLORS.start;
    }
    if (label === goalSelect.value) {
        return COLORS.goal;
    }
    if (finalPathNodes.has(label)) {
        return COLORS.path;
    }
    if (exploredNodes.has(label)) {
        return COLORS.explored;
    }
    return COLORS.node;
}

function drawNode(label) {
    const [x, y] = coordinates(label);
    const radius = graph.canvas.node_radius;
    const color = nodeColor(label);
    const scale = drawingScale();

    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.fillStyle = color;
    context.fill();

    // Node outline
    if (color === COLORS.node) {
        context.strokeStyle = COLORS.nodeBorder;
        context.lineWidth = 2.5 * scale;
    } else {
        context.strokeStyle = "#FFFFFF";
        context.lineWidth = 2 * scale;
    }
    context.stroke();

    // Node Text
    const isSolidNode = color !== COLORS.node;
    context.fillStyle = isSolidNode ? COLORS.white : COLORS.nodeText;
    context.font = `bold ${13 * scale}px "Roboto", Arial, sans-serif`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(label, x, y + 0.5 * scale);
}

function roundedRectangle(x, y, width, height, radius) {
    const right = x + width;
    const bottom = y + height;
    context.beginPath();
    context.moveTo(x + radius, y);
    context.lineTo(right - radius, y);
    context.quadraticCurveTo(right, y, right, y + radius);
    context.lineTo(right, bottom - radius);
    context.quadraticCurveTo(right, bottom, right - radius, bottom);
    context.lineTo(x + radius, bottom);
    context.quadraticCurveTo(x, bottom, x, bottom - radius);
    context.lineTo(x, y + radius);
    context.quadraticCurveTo(x, y, x + radius, y);
    context.closePath();
}

function drawWeightLabel(edge) {
    const [x1, y1] = coordinates(edge.from);
    const [x2, y2] = coordinates(edge.to);
    const dx = x2 - x1;
    const dy = y2 - y1;
    const length = Math.hypot(dx, dy);
    const scale = drawingScale();
    const offset = 13 * scale;
    const x = (x1 + x2) / 2 + (-dy * offset) / length;
    const y = (y1 + y2) / 2 + (dx * offset) / length;
    const text = edge.weight.toFixed(1);

    context.font = `bold ${11 * scale}px "Roboto Mono", Consolas, monospace`;
    const width = context.measureText(text).width + 10 * scale;
    const height = 18 * scale;
    roundedRectangle(x - width / 2, y - height / 2, width, height, 4 * scale);
    context.fillStyle = COLORS.distanceBackground;
    context.fill();
    context.strokeStyle = COLORS.distanceBorder;
    context.lineWidth = 1 * scale;
    context.stroke();

    context.fillStyle = COLORS.distanceText;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(text, x, y + 0.5 * scale);
}

function drawScene() {
    context.clearRect(0, 0, canvas.width, canvas.height);
    if (mapLoaded) {
        context.drawImage(mapImage, 0, 0, canvas.width, canvas.height);
    } else {
        drawFallbackBackground();
    }

    if (!graph) {
        return;
    }

    // 1. Draw base edges
    graph.edges.forEach((edge) => drawEdge(edge, COLORS.edge, 3.5));

    // 2. Draw completed explored edges
    completedExploredEdges.forEach((edge) => drawEdge(edge, COLORS.explored, 3.5));

    // 3. Draw completed shortest path edges
    completedPathEdges.forEach((edge) => drawEdge(edge, COLORS.path, 5.5));

    // 4. Draw active animated segment
    if (activeSegment) {
        drawEdge(
            activeSegment.edge,
            activeSegment.color,
            activeSegment.width,
            activeSegment.progress,
        );
    }

    // 5. Draw nodes
    graph.labels.forEach(drawNode);

    // 6. Draw weights if enabled
    if (showWeights) {
        graph.edges.forEach(drawWeightLabel);
    }
}

function clearRouteState() {
    completedExploredEdges = [];
    completedPathEdges = [];
    exploredNodes = new Set();
    finalPathNodes = new Set();
    activeSegment = null;
}

function clearResults() {
    currentResult = null;
    currentRequest = null;
    
    // Encrypted Export
    if (encryptedExport) {
        encryptedExport.textContent = "Run a path first to serialize and encrypt the route.";
    }
    if (decryptedVerificationBox) {
        decryptedVerificationBox.textContent = "Awaiting A* execution…";
    }
    if (encryptionStatus) {
        encryptionStatus.textContent = "🔒 Protected";
        encryptionStatus.className = "badge badge-neutral";
    }
    if (downloadButton) {
        downloadButton.disabled = true;
    }
    if (copyCiphertextButton) {
        copyCiphertextButton.disabled = true;
    }

    // Shortest Route Card
    if (routeResultStatusBadge) {
        routeResultStatusBadge.textContent = "● Ready";
        routeResultStatusBadge.className = "badge badge-neutral";
    }
    if (routeMetricDistance) routeMetricDistance.textContent = "—";
    if (routeMetricNodes) routeMetricNodes.textContent = "—";
    if (routeMetricStatus) routeMetricStatus.textContent = "Awaiting Search";
    if (routeSequenceDisplay) {
        routeSequenceDisplay.innerHTML = '<span class="placeholder-text">Run A* to compute the optimal shortest path.</span>';
    }

    // Table view
    if (computationTableBody) {
        computationTableBody.innerHTML = `
            <tr class="empty-row">
                <td colspan="7">Awaiting weighted A* execution… Select start and goal nodes, then click Run A*.</td>
            </tr>
        `;
    }
}

function cancelAnimation() {
    animationToken += 1;
    setBusy(false);
}

function reset({ clearLog = true } = {}) {
    cancelAnimation();
    clearRouteState();
    clearResults();
    if (runStatus) {
        runStatus.textContent = "Ready";
        runStatus.className = "badge badge-primary";
    }
    if (clearLog && algorithmLog) {
        logSequence = 0;
        stepCounter = 0;
        algorithmLog.textContent = "[000] Awaiting weighted A* execution…";
    }
    drawScene();
}

function beginLog() {
    logSequence = 0;
    stepCounter = 0;
    if (algorithmLog) algorithmLog.textContent = "";
    if (computationTableBody) computationTableBody.innerHTML = "";
}

function appendLog(message) {
    logSequence += 1;
    if (algorithmLog) {
        algorithmLog.textContent += `[${String(logSequence).padStart(3, "0")}] ${message}\n`;
        algorithmLog.scrollTop = algorithmLog.scrollHeight;
    }
}

function addTableRow({ step, edge, weight, g, h, f, status = "Explored", isOptimal = false }) {
    if (!computationTableBody) return;
    
    const row = document.createElement("tr");
    if (isOptimal) {
        row.className = "optimal-row";
    }
    
    row.innerHTML = `
        <td class="mono-cell">#${String(step).padStart(2, "0")}</td>
        <td><strong>${edge}</strong></td>
        <td class="mono-cell">${typeof weight === "number" ? weight.toFixed(1) : weight}</td>
        <td class="mono-cell">${typeof g === "number" ? g.toFixed(1) : g}</td>
        <td class="mono-cell">${typeof h === "number" ? h.toFixed(1) : h}</td>
        <td class="mono-cell"><strong>${typeof f === "number" ? f.toFixed(1) : f}</strong></td>
        <td>${status}</td>
    `;
    computationTableBody.appendChild(row);
    
    // Auto-scroll table container to bottom
    if (tableViewContainer) {
        tableViewContainer.scrollTop = tableViewContainer.scrollHeight;
    }
}

async function animateEdge(edge, color, width, token) {
    for (let step = 1; step <= STEPS; step += 1) {
        if (token !== animationToken) {
            return false;
        }
        activeSegment = { edge, color, width, progress: step / STEPS };
        drawScene();
        await delay(STEP_DELAY);
    }

    activeSegment = null;
    if (color === COLORS.path) {
        completedPathEdges.push(edge);
    } else {
        completedExploredEdges.push(edge);
    }
    drawScene();
    await delay(EDGE_PAUSE);
    return token === animationToken;
}

function renderRouteResults(result) {
    const start = startSelect.value;
    const goal = goalSelect.value;
    const totalCost = result.total_cost !== null ? result.total_cost.toFixed(1) : "N/A";
    const pathNodes = result.path;

    // Metrics
    if (routeMetricDistance) routeMetricDistance.textContent = totalCost;
    if (routeMetricNodes) routeMetricNodes.textContent = String(pathNodes.length);
    if (routeMetricStatus) routeMetricStatus.textContent = "Shortest Path Confirmed";
    
    if (routeResultStatusBadge) {
        routeResultStatusBadge.textContent = "● Shortest Path Found";
        routeResultStatusBadge.className = "badge badge-success";
    }

    // Sequence chips
    if (routeSequenceDisplay) {
        routeSequenceDisplay.innerHTML = "";
        pathNodes.forEach((node, index) => {
            const chip = document.createElement("span");
            chip.className = "route-node-chip";
            if (node === start) chip.classList.add("start");
            else if (node === goal) chip.classList.add("goal");
            chip.textContent = node;
            routeSequenceDisplay.appendChild(chip);

            if (index < pathNodes.length - 1) {
                const arrow = document.createElement("span");
                arrow.className = "route-node-arrow";
                arrow.textContent = "→";
                routeSequenceDisplay.appendChild(arrow);
            }
        });
    }

    // Encrypted Export & Verification
    const shift = result.shift ?? result.cipher_key;
    if (cryptoActiveShift) cryptoActiveShift.textContent = shift;
    
    if (encryptedExport) {
        encryptedExport.textContent = result.ciphertext;
    }
    if (decryptedVerificationBox) {
        decryptedVerificationBox.textContent = `Path: ${result.path.join(" → ")}\nWeights: [${result.edge_weights.map(w => w.toFixed(1)).join(", ")}]\nTotal: ${totalCost} (Shift: ${shift})`;
    }
    if (encryptionStatus) {
        encryptionStatus.textContent = "🔓 Encrypted & Verified";
        encryptionStatus.className = "badge badge-success";
    }
    if (downloadButton) {
        downloadButton.disabled = false;
    }
    if (copyCiphertextButton) {
        copyCiphertextButton.disabled = false;
    }
}

async function animateResult(result, token) {
    const start = startSelect.value;
    const goal = goalSelect.value;

    appendLog(`A* initialized with original graph weights.`);
    appendLog(`Start node: ${start} | Goal node: ${goal} | h(start)=${result.start_cost.h.toFixed(1)}`);

    // Add initial start node row to table
    addTableRow({
        step: 0,
        edge: `${start} (Start)`,
        weight: 0.0,
        g: 0.0,
        h: result.start_cost.h,
        f: result.start_cost.f,
        status: "Root node queued",
    });

    for (const edge of result.explored) {
        if (token !== animationToken) {
            return;
        }
        stepCounter += 1;
        appendLog(`Exploring ${edge.from} → ${edge.to} (Weight: ${edge.weight.toFixed(1)}, g=${edge.g.toFixed(1)}, h=${edge.h.toFixed(1)}, f=${edge.f.toFixed(1)})`);
        
        addTableRow({
            step: stepCounter,
            edge: `${edge.from} → ${edge.to}`,
            weight: edge.weight,
            g: edge.g,
            h: edge.h,
            f: edge.f,
            status: edge.to === goal ? "Goal node reached" : "Open set evaluation",
        });

        if (edge.to !== goal) {
            exploredNodes.add(edge.to);
        }
        drawScene();
        if (!(await animateEdge(edge, COLORS.explored, 3.5, token))) {
            return;
        }
    }

    appendLog("Goal reached. Optimal shortest path confirmed.");
    appendLog(`Shortest path: ${result.path.join(" → ")}`);
    appendLog(`Total cost: ${result.total_cost.toFixed(1)}`);
    if (runStatus) {
        runStatus.textContent = "Drawing Route";
        runStatus.className = "badge badge-primary";
    }

    for (const edge of result.path_edges) {
        if (token !== animationToken) {
            return;
        }
        finalPathNodes.add(edge.from);
        finalPathNodes.add(edge.to);
        drawScene();
        if (!(await animateEdge(edge, COLORS.path, 5.5, token))) {
            return;
        }
    }

    if (token !== animationToken) {
        return;
    }

    const shift = result.shift ?? result.cipher_key;
    appendLog("--- WAYCIPHER Cryptography Execution ---");
    appendLog(`Serialized Route: ${result.serialized_route}`);
    appendLog(`Caesar Encrypt (Shift ${shift}): ${result.ciphertext}`);
    appendLog(`Round-Trip Verified: ${result.serialized_route}`);
    appendLog(`Ready for download: route_${start}_${goal}.txt`);

    // Add summary row to table
    addTableRow({
        step: stepCounter + 1,
        edge: `${result.path.join(" → ")}`,
        weight: result.total_cost,
        g: result.total_cost,
        h: 0.0,
        f: result.total_cost,
        status: "★ Optimal Shortest Path",
        isOptimal: true,
    });

    renderRouteResults(result);
    setBusy(false);
    if (runStatus) {
        runStatus.textContent = "Complete";
        runStatus.className = "badge badge-success";
    }
}

async function requestWorkflow(start, goal, shift) {
    const response = await fetch("/api/astar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start, goal, shift: shift, cipher_key: shift }),
    });
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.error || "Unable to run weighted A* search.");
    }
    return result;
}

async function runAStar() {
    if (!graph) {
        return;
    }

    reset();
    const token = animationToken;
    const start = startSelect.value;
    const goal = goalSelect.value;
    const shift = Number(cipherKeyInput.value);

    setBusy(true);
    beginLog();
    appendLog("Starting weighted A* search.");
    appendLog(`Start: ${start} | Goal: ${goal} | Caesar Shift: ${shift}`);
    
    if (runStatus) {
        runStatus.textContent = "Searching...";
        runStatus.className = "badge badge-primary";
    }
    if (routeResultStatusBadge) {
        routeResultStatusBadge.textContent = "● Searching...";
        routeResultStatusBadge.className = "badge badge-primary";
    }

    try {
        const result = await requestWorkflow(start, goal, shift);
        if (token !== animationToken) {
            return;
        }
        currentResult = result;
        currentRequest = { start, goal };
        await animateResult(result, token);
    } catch (error) {
        if (token === animationToken) {
            appendLog(`ERROR: ${error.message}`);
            if (runStatus) {
                runStatus.textContent = "Error";
                runStatus.className = "badge badge-neutral";
            }
            if (routeResultStatusBadge) {
                routeResultStatusBadge.textContent = "● Search Error";
                routeResultStatusBadge.className = "badge badge-neutral";
            }
            setBusy(false);
        }
    }
}

async function refreshEncryption() {
    if (!currentResult || !currentRequest) {
        return;
    }

    const shift = Number(cipherKeyInput.value);
    downloadButton.disabled = true;
    if (copyCiphertextButton) copyCiphertextButton.disabled = true;
    if (encryptionStatus) {
        encryptionStatus.textContent = "Encrypting…";
        encryptionStatus.className = "badge badge-neutral";
    }
    
    try {
        const updated = await requestWorkflow(currentRequest.start, currentRequest.goal, shift);
        const samePath = updated.path.join("|") === currentResult.path.join("|");
        const sameCost = updated.total_cost === currentResult.total_cost;
        if (!samePath || !sameCost) {
            throw new Error("Caesar shift unexpectedly modified shortest path!");
        }
        currentResult = updated;
        renderRouteResults(updated);
        appendLog(`Shift updated to ${shift}; optimal path (${updated.path.join(" → ")}) and cost (${updated.total_cost.toFixed(1)}) remained unchanged.`);
        appendLog(`New ciphertext: ${updated.ciphertext}`);
    } catch (error) {
        if (encryptedExport) encryptedExport.textContent = `Error: ${error.message}`;
        if (encryptionStatus) {
            encryptionStatus.textContent = "Error";
            encryptionStatus.className = "badge badge-neutral";
        }
    }
}

function populateNodeSelectors(labels) {
    labels.forEach((label) => {
        startSelect.add(new Option(`Node ${label}`, label));
        goalSelect.add(new Option(`Node ${label}`, label));
    });
    startSelect.value = "A";
    goalSelect.value = "T";
}

async function loadGraph() {
    try {
        const response = await fetch("/api/graph");
        if (!response.ok) {
            throw new Error("Unable to load weighted graph data.");
        }
        graph = await response.json();
        canvas.width = graph.canvas.width;
        canvas.height = graph.canvas.height;
        populateNodeSelectors(graph.labels);
        drawScene();
    } catch (error) {
        if (mapStatus) {
            mapStatus.textContent = "● Graph Offline";
            mapStatus.className = "badge badge-neutral";
        }
        if (algorithmLog) algorithmLog.textContent = `[ERR] ${error.message}`;
        if (runStatus) {
            runStatus.textContent = "Offline";
            runStatus.className = "badge badge-neutral";
        }
    }
}

async function downloadEncryptedText() {
    if (!currentResult || !currentRequest) {
        return;
    }

    downloadButton.disabled = true;
    try {
        const shift = currentResult.shift ?? currentResult.cipher_key;
        const response = await fetch("/api/download", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                start: currentRequest.start,
                goal: currentRequest.goal,
                shift: shift,
                cipher_key: shift,
            }),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || "Unable to download encrypted route.");
        }

        const blob = await response.blob();
        const disposition = response.headers.get("Content-Disposition") || "";
        const filenameMatch = disposition.match(/filename\*?=(?:UTF-8''|\")?([^\";]+)/i);
        const filename = filenameMatch
            ? decodeURIComponent(filenameMatch[1].replace(/\"/g, ""))
            : `route_${currentRequest.start}_${currentRequest.goal}.txt`;
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        appendLog(`Downloaded ciphertext file: ${filename}`);
    } catch (error) {
        appendLog(`DOWNLOAD ERROR: ${error.message}`);
    } finally {
        downloadButton.disabled = false;
    }
}

function copyCiphertext() {
    if (!currentResult || !currentResult.ciphertext) return;
    navigator.clipboard.writeText(currentResult.ciphertext).then(() => {
        const originalText = copyCiphertextButton.innerHTML;
        copyCiphertextButton.innerHTML = `<span style="color: var(--color-success-text); font-weight: 600;">Copied!</span>`;
        setTimeout(() => {
            copyCiphertextButton.innerHTML = originalText;
        }, 1600);
    }).catch(() => {
        appendLog("Clipboard copy failed.");
    });
}

// Event Listeners
runButton.addEventListener("click", runAStar);
resetButton.addEventListener("click", () => reset());
downloadButton.addEventListener("click", downloadEncryptedText);
if (copyCiphertextButton) {
    copyCiphertextButton.addEventListener("click", copyCiphertext);
}

showDistanceButton.addEventListener("click", () => {
    showWeights = true;
    showDistanceButton.classList.add("active");
    hideDistanceButton.classList.remove("active");
    drawScene();
});

hideDistanceButton.addEventListener("click", () => {
    showWeights = false;
    hideDistanceButton.classList.add("active");
    showDistanceButton.classList.remove("active");
    drawScene();
});

[startSelect, goalSelect].forEach((select) => {
    select.addEventListener("change", () => reset({ clearLog: false }));
});

cipherKeyInput.addEventListener("input", () => {
    const shift = cipherKeyInput.value;
    cipherKeyValue.textContent = shift;
    if (cryptoActiveShift) cryptoActiveShift.textContent = shift;
    if (currentResult) {
        downloadButton.disabled = true;
        if (copyCiphertextButton) copyCiphertextButton.disabled = true;
        if (encryptionStatus) {
            encryptionStatus.textContent = "Shift modified";
            encryptionStatus.className = "badge badge-neutral";
        }
    }
});

cipherKeyInput.addEventListener("change", refreshEncryption);

// Tab switching for Computation Log
if (tabTableView && tabRawLogView) {
    tabTableView.addEventListener("click", () => {
        tabTableView.classList.add("active");
        tabTableView.setAttribute("aria-selected", "true");
        tabRawLogView.classList.remove("active");
        tabRawLogView.setAttribute("aria-selected", "false");
        tableViewContainer.classList.remove("hidden");
        rawLogViewContainer.classList.add("hidden");
    });

    tabRawLogView.addEventListener("click", () => {
        tabRawLogView.classList.add("active");
        tabRawLogView.setAttribute("aria-selected", "true");
        tabTableView.classList.remove("active");
        tabTableView.setAttribute("aria-selected", "false");
        rawLogViewContainer.classList.remove("hidden");
        tableViewContainer.classList.add("hidden");
    });
}

// Redraw canvas on window resize to ensure crispness
window.addEventListener("resize", () => {
    if (graph) {
        drawScene();
    }
});

canvas.addEventListener("click", (event) => {
    if (!DEBUG_COORDINATES) {
        return;
    }
    const rectangle = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rectangle.width;
    const scaleY = canvas.height / rectangle.height;
    const x = (event.clientX - rectangle.left) * scaleX;
    const y = (event.clientY - rectangle.top) * scaleY;
    console.log(`Canvas X: ${x.toFixed(1)}, Canvas Y: ${y.toFixed(1)}`);
});

// Initialization
loadGraph();
