"use strict";

/**
 * GraphCrypt dark interface color tokens.
 */
const COLORS = {
    fallback: "#E9EDF3",
    fallbackGrid: "rgba(71, 85, 105, 0.12)",
    edgeOutline: "rgba(255, 255, 255, 0.92)",
    edge: "#536277",
    node: "#FFFFFF",
    nodeBorder: "#6857D9",
    nodeText: "#172033",
    explored: "#0891B2",
    start: "#0F9F8E",
    goal: "#E54862",
    path: "#6857D9",
    white: "#FFFFFF",
    dark: "#080C14",
    distanceBackground: "rgba(255, 255, 255, 0.94)",
    distanceBorder: "#AAB5C4",
    distanceText: "#172033",
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
const runButton = document.querySelector("#runButton");
const resetButton = document.querySelector("#resetButton");
const showDistanceButton = document.querySelector("#showDistanceButton");
const hideDistanceButton = document.querySelector("#hideDistanceButton");
const downloadRouteButton = document.querySelector("#downloadRouteButton");
const algorithmLog = document.querySelector("#algorithmLog");
const runStatus = document.querySelector("#runStatus");
const systemEngineStatus = document.querySelector("#systemEngineStatus");

// Result card elements
const routeResultStatusBadge = document.querySelector("#routeResultStatusBadge");
const routeMetricDistance = document.querySelector("#routeMetricDistance");
const routeMetricNodes = document.querySelector("#routeMetricNodes");
const routeMetricVisited = document.querySelector("#routeMetricVisited");
const routeMetricStatus = document.querySelector("#routeMetricStatus");
const routeSequenceDisplay = document.querySelector("#routeSequenceDisplay");
const routeVisitedNodesDisplay = document.querySelector("#routeVisitedNodesDisplay");
const routeSerializedOutput = document.querySelector("#routeSerializedOutput");
const routeExportStatus = document.querySelector("#routeExportStatus");
const mapCipherKey = document.querySelector("#mapCipherKey");
const mapCipherKeyValue = document.querySelector("#mapCipherKeyValue");

// Tab controls for computation log
const tabTableView = document.querySelector("#tabTableView");
const tabRawLogView = document.querySelector("#tabRawLogView");
const tableViewContainer = document.querySelector("#tableViewContainer");
const rawLogViewContainer = document.querySelector("#rawLogViewContainer");
const computationTableBody = document.querySelector("#computationTableBody");

// Main page and Cipher subsection tabs
const mapPageTab = document.querySelector("#mapPageTab");
const cipherPageTab = document.querySelector("#cipherPageTab");
const textPageTab = document.querySelector("#textPageTab");
const mapPagePanel = document.querySelector("#mapPagePanel");
const cipherPagePanel = document.querySelector("#cipherPagePanel");
const textPagePanel = document.querySelector("#textPagePanel");
const encryptTab = document.querySelector("#encryptTab");
const decryptTab = document.querySelector("#decryptTab");
const encryptPanel = document.querySelector("#encryptPanel");
const decryptPanel = document.querySelector("#decryptPanel");

// Encrypt workflow controls
const encryptTextInput = document.querySelector("#encryptTextInput");
const encryptFileInput = document.querySelector("#encryptFileInput");
const encryptFileName = document.querySelector("#encryptFileName");
const encryptCipherKey = document.querySelector("#encryptCipherKey");
const encryptCipherKeyValue = document.querySelector("#encryptCipherKeyValue");
const encryptButton = document.querySelector("#encryptButton");
const encryptOutput = document.querySelector("#encryptOutput");
const encryptError = document.querySelector("#encryptError");
const encryptStatus = document.querySelector("#encryptStatus");
const copyCiphertextButton = document.querySelector("#copyCiphertextButton");
const downloadEncryptedButton = document.querySelector("#downloadEncryptedButton");
const useInDecryptButton = document.querySelector("#useInDecryptButton");

// Decrypt workflow controls
const decryptTextInput = document.querySelector("#decryptTextInput");
const decryptFileInput = document.querySelector("#decryptFileInput");
const decryptFileName = document.querySelector("#decryptFileName");
const decryptCipherKey = document.querySelector("#decryptCipherKey");
const decryptCipherKeyValue = document.querySelector("#decryptCipherKeyValue");
const decryptButton = document.querySelector("#decryptButton");
const decryptOutput = document.querySelector("#decryptOutput");
const decryptError = document.querySelector("#decryptError");
const decryptStatus = document.querySelector("#decryptStatus");
const copyDecryptedButton = document.querySelector("#copyDecryptedButton");
const downloadDecryptedButton = document.querySelector("#downloadDecryptedButton");

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

const cipherState = {
    encrypt: { file: null, result: null, operation: 0, busy: false, downloadBusy: false },
    decrypt: { file: null, result: null, operation: 0, busy: false, downloadBusy: false },
};
let routeDownloadBusy = false;
let mapCiphertextResult = null;
let mapEncryptionOperation = 0;
let mapEncryptionBusy = false;

// Map image loading
const mapImage = new Image();
mapImage.src = "/static/images/argentina_map.png";
mapImage.addEventListener("load", () => {
    mapLoaded = true;
    drawScene();
});
mapImage.addEventListener("error", () => {
    mapLoaded = false;
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
    runButton.disabled = isBusy || !graph;
    startSelect.disabled = isBusy;
    goalSelect.disabled = isBusy;
    if (mapCipherKey) mapCipherKey.disabled = isBusy || mapEncryptionBusy || !graph;
}

function setMapEncryptionBusy(isBusy) {
    mapEncryptionBusy = isBusy;
    if (mapCipherKey) {
        mapCipherKey.disabled = isBusy || Boolean(startSelect?.disabled) || !graph;
    }
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

    const scale = drawingScale();

    // A light casing keeps every connection readable over street names and map detail.
    context.beginPath();
    context.moveTo(x1, y1);
    context.lineTo(endX, endY);
    context.strokeStyle = COLORS.edgeOutline;
    context.lineWidth = (width + 2.4) * scale;
    context.lineCap = "round";
    context.stroke();

    context.beginPath();
    context.moveTo(x1, y1);
    context.lineTo(endX, endY);
    context.strokeStyle = color;
    context.lineWidth = width * scale;
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
        context.strokeStyle = "#F7FAFF";
        context.lineWidth = 2 * scale;
    }
    context.stroke();

    // Node Text
    const isSolidNode = color !== COLORS.node;
    context.fillStyle = isSolidNode ? COLORS.white : COLORS.nodeText;
    context.font = `700 ${13 * scale}px "Manrope", Arial, sans-serif`;
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

    context.font = `600 ${11 * scale}px "IBM Plex Mono", Consolas, monospace`;
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
        context.save();
        context.filter = "saturate(0.58) brightness(0.93) contrast(0.96)";
        context.drawImage(mapImage, 0, 0, canvas.width, canvas.height);
        context.restore();
        context.fillStyle = "rgba(244, 247, 251, 0.08)";
        context.fillRect(0, 0, canvas.width, canvas.height);
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
    mapEncryptionOperation += 1;
    mapCiphertextResult = null;
    mapEncryptionBusy = false;

    // Shortest Route Card
    if (routeResultStatusBadge) {
        routeResultStatusBadge.textContent = "● Ready";
        routeResultStatusBadge.className = "badge badge-neutral";
    }
    if (routeMetricDistance) routeMetricDistance.textContent = "—";
    if (routeMetricNodes) routeMetricNodes.textContent = "—";
    if (routeMetricVisited) routeMetricVisited.textContent = "—";
    if (routeMetricStatus) routeMetricStatus.textContent = "Awaiting Search";
    if (routeSequenceDisplay) {
        routeSequenceDisplay.innerHTML = '<span class="placeholder-text">Run A* to compute the optimal shortest path.</span>';
    }
    if (routeVisitedNodesDisplay) routeVisitedNodesDisplay.textContent = "Awaiting search";
    if (routeSerializedOutput) {
        routeSerializedOutput.textContent = "Run A* to encrypt the route with the selected Caesar shift.";
    }
    setStatus(routeExportStatus, "Not available", "neutral");
    if (downloadRouteButton) {
        downloadRouteButton.disabled = true;
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

async function renderRouteResults(result, token = animationToken) {
    const start = startSelect.value;
    const goal = goalSelect.value;
    const totalCost = result.total_cost !== null ? result.total_cost.toFixed(1) : "N/A";
    const pathNodes = result.path;
    const visitedNodes = Array.isArray(result.visited_nodes) ? result.visited_nodes : [];

    // Metrics
    if (routeMetricDistance) routeMetricDistance.textContent = totalCost;
    if (routeMetricNodes) routeMetricNodes.textContent = String(pathNodes.length);
    if (routeMetricVisited) routeMetricVisited.textContent = String(visitedNodes.length);
    if (routeMetricStatus) routeMetricStatus.textContent = "Shortest Path Confirmed";
    if (routeVisitedNodesDisplay) {
        routeVisitedNodesDisplay.textContent = visitedNodes.length ? visitedNodes.join(" → ") : "None";
    }
    
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
    if (routeSerializedOutput) {
        routeSerializedOutput.textContent = "Encrypting route with the selected Caesar shift...";
    }
    if (downloadRouteButton) downloadRouteButton.disabled = true;
    await refreshMapEncryption(result, token);
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
    if (Array.isArray(result.visited_nodes)) {
        appendLog(`Visited nodes (${result.visited_nodes.length}): ${result.visited_nodes.join(" → ")}`);
    }
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

    appendLog(`Serialized Route: ${result.serialized_route}`);
    appendLog("Applying the selected Caesar shift to the serialized route.");

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

    await renderRouteResults(result, token);
    if (token !== animationToken) {
        return;
    }
    setBusy(false);
    if (runStatus) {
        runStatus.textContent = "Complete";
        runStatus.className = "badge badge-success";
    }
}

async function requestAStar(start, goal) {
    const response = await fetch("/api/astar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start, goal }),
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

    setBusy(true);
    beginLog();
    appendLog("Starting weighted A* search.");
    appendLog(`Start: ${start} | Goal: ${goal}`);
    
    if (runStatus) {
        runStatus.textContent = "Searching...";
        runStatus.className = "badge badge-primary";
    }
    if (routeResultStatusBadge) {
        routeResultStatusBadge.textContent = "● Searching...";
        routeResultStatusBadge.className = "badge badge-primary";
    }

    try {
        const result = await requestAStar(start, goal);
        if (token !== animationToken) {
            return;
        }
        if (!Array.isArray(result.path) || !result.path.length || result.total_cost === null) {
            throw new Error(`No route exists between start node ${start} and goal node ${goal}.`);
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
            if (routeMetricStatus) routeMetricStatus.textContent = error.message;
            if (routeVisitedNodesDisplay) routeVisitedNodesDisplay.textContent = "Search failed";
            setBusy(false);
        }
    }
}

async function postJson(url, body) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });

    let payload = null;
    try {
        payload = await response.json();
    } catch (_error) {
        // A non-JSON response is converted into the same clear workflow error.
    }
    if (!response.ok) {
        throw new Error(payload?.error || "The server could not process this file.");
    }
    return payload;
}

async function refreshMapEncryption(result, token = animationToken) {
    let shift;
    try {
        shift = validateCipherShift(mapCipherKey);
    } catch (error) {
        mapCiphertextResult = null;
        if (routeSerializedOutput) routeSerializedOutput.textContent = `Encryption error: ${error.message}`;
        setStatus(routeExportStatus, "Invalid shift", "error");
        return false;
    }

    const operation = ++mapEncryptionOperation;
    mapCiphertextResult = null;
    if (downloadRouteButton) downloadRouteButton.disabled = true;
    setMapEncryptionBusy(true);
    setStatus(routeExportStatus, `Encrypting (shift ${shift})...`, "primary");

    try {
        const start = currentRequest?.start || startSelect.value;
        const goal = currentRequest?.goal || goalSelect.value;
        const encrypted = await postJson("/api/encrypt", {
            plaintext: result.serialized_route,
            shift,
            filename: `route_${start}_${goal}.txt`,
        });

        if (operation !== mapEncryptionOperation || token !== animationToken) {
            return false;
        }

        const samePath = Array.isArray(encrypted.path)
            && encrypted.path.join("|") === result.path.join("|");
        const sameCost = Number(encrypted.total_cost) === Number(result.total_cost);
        if (!samePath || !sameCost) {
            throw new Error("Caesar encryption unexpectedly modified the optimal route.");
        }

        mapCiphertextResult = encrypted;
        if (routeSerializedOutput) {
            routeSerializedOutput.textContent = `Ciphertext:\n${encrypted.ciphertext}`;
        }
        setStatus(routeExportStatus, `Encrypted (shift ${shift})`, "success");
        if (downloadRouteButton) downloadRouteButton.disabled = false;
        appendLog(`Caesar encryption complete (shift ${shift}).`);
        appendLog(`Encrypted route ready for download: route_${start}_${goal}.txt`);
        return true;
    } catch (error) {
        if (operation !== mapEncryptionOperation || token !== animationToken) {
            return false;
        }
        mapCiphertextResult = null;
        if (routeSerializedOutput) routeSerializedOutput.textContent = `Encryption error: ${error.message}`;
        setStatus(routeExportStatus, "Encryption failed", "error");
        appendLog(`ENCRYPTION ERROR: ${error.message}`);
        return false;
    } finally {
        if (operation === mapEncryptionOperation) {
            setMapEncryptionBusy(false);
        }
    }
}

function validateCipherShift(input) {
    const rawValue = String(input?.value ?? "").trim();
    if (!/^\d+$/.test(rawValue)) {
        throw new Error("Caesar shift must be a whole number from 0 to 25.");
    }
    const shift = Number(rawValue);
    if (!Number.isInteger(shift) || shift < 0 || shift > 25) {
        throw new Error("Caesar shift must be between 0 and 25.");
    }
    return shift;
}

function setStatus(element, text, state = "neutral") {
    if (!element) return;
    element.textContent = text;
    element.className = `badge badge-${state}`;
    element.dataset.state = state;
}

function setError(element, message = "") {
    if (!element) return;
    element.textContent = message;
    element.hidden = !message;
}

function updateRangeFill(input, valueDisplay) {
    if (!input) return;
    const minimum = Number(input.min) || 0;
    const maximum = Number(input.max) || 25;
    const current = Number(input.value);
    const progress = ((current - minimum) / (maximum - minimum)) * 100;
    input.style.setProperty("--range-progress", `${progress}%`);
    if (valueDisplay) valueDisplay.textContent = input.value;
}

function resetEncryptResult({ preserveError = false } = {}) {
    cipherState.encrypt.result = null;
    if (encryptOutput) encryptOutput.textContent = "Ciphertext will appear here after you press Encrypt.";
    if (copyCiphertextButton) copyCiphertextButton.disabled = true;
    if (downloadEncryptedButton) downloadEncryptedButton.disabled = true;
    if (useInDecryptButton) useInDecryptButton.disabled = true;
    if (!preserveError) setError(encryptError);
}

function resetDecryptResult({ preserveError = false } = {}) {
    cipherState.decrypt.result = null;
    if (decryptOutput) decryptOutput.textContent = "The original plaintext will appear here after you press Decrypt.";
    if (copyDecryptedButton) copyDecryptedButton.disabled = true;
    if (downloadDecryptedButton) downloadDecryptedButton.disabled = true;
    if (!preserveError) setError(decryptError);
}

function hasCipherInput(kind) {
    const textInput = kind === "encrypt" ? encryptTextInput : decryptTextInput;
    return Boolean(textInput?.value.trim() || cipherState[kind].file);
}

function syncCipherActionState(kind) {
    const actionButton = kind === "encrypt" ? encryptButton : decryptButton;
    if (actionButton) {
        actionButton.disabled = cipherState[kind].busy;
    }
}

function setCipherBusy(kind, isBusy) {
    const encrypting = kind === "encrypt";
    const textInput = encrypting ? encryptTextInput : decryptTextInput;
    const fileInput = encrypting ? encryptFileInput : decryptFileInput;
    const keyInput = encrypting ? encryptCipherKey : decryptCipherKey;
    const actionButton = encrypting ? encryptButton : decryptButton;
    cipherState[kind].busy = isBusy;
    if (textInput) textInput.disabled = isBusy;
    if (fileInput) fileInput.disabled = isBusy;
    if (keyInput) keyInput.disabled = isBusy;
    if (actionButton) {
        actionButton.disabled = isBusy;
        actionButton.classList.toggle("is-loading", isBusy);
        actionButton.setAttribute("aria-busy", String(isBusy));
    }
}

function isTextFile(file) {
    return Boolean(file && /\.txt$/i.test(file.name));
}

function selectCipherFile(kind) {
    const encrypting = kind === "encrypt";
    const input = encrypting ? encryptFileInput : decryptFileInput;
    const filename = encrypting ? encryptFileName : decryptFileName;
    const errorBox = encrypting ? encryptError : decryptError;
    const status = encrypting ? encryptStatus : decryptStatus;
    const state = cipherState[kind];
    const uploadZone = input?.closest(".file-upload-zone");

    state.operation += 1;
    state.file = null;
    if (encrypting) resetEncryptResult();
    else resetDecryptResult();

    const file = input?.files?.[0] || null;
    if (!file) {
        if (filename) {
            filename.textContent = "No file selected";
            filename.classList.add("is-empty");
            filename.dataset.empty = "true";
        }
        uploadZone?.classList.remove("has-file", "is-selected");
        syncCipherActionState(kind);
        setStatus(status, hasCipherInput(kind) ? `Ready to ${kind}` : "Awaiting input", "neutral");
        return;
    }

    if (!isTextFile(file)) {
        if (filename) {
            filename.textContent = `${file.name} — unsupported`;
            filename.classList.remove("is-empty");
            filename.dataset.empty = "false";
        }
        uploadZone?.classList.remove("has-file", "is-selected");
        if (input) input.value = "";
        syncCipherActionState(kind);
        setError(errorBox, "Invalid file type. Select a .txt file.");
        setStatus(status, "Invalid file", "error");
        return;
    }

    state.file = file;
    if (filename) {
        filename.textContent = file.name;
        filename.classList.remove("is-empty");
        filename.dataset.empty = "false";
    }
    uploadZone?.classList.add("has-file", "is-selected");
    // Keep the File in workflow state while allowing the same file to be
    // selected again and still emit a native change event.
    if (input) input.value = "";
    syncCipherActionState(kind);
    setError(errorBox);
    setStatus(status, encrypting ? "Ready to encrypt" : "Ready to decrypt", "primary");
}

function clearSelectedCipherFile(kind) {
    const encrypting = kind === "encrypt";
    const input = encrypting ? encryptFileInput : decryptFileInput;
    const filename = encrypting ? encryptFileName : decryptFileName;
    const uploadZone = input?.closest(".file-upload-zone");
    cipherState[kind].file = null;
    if (input) input.value = "";
    if (filename) {
        filename.textContent = "No file selected";
        filename.classList.add("is-empty");
        filename.dataset.empty = "true";
    }
    uploadZone?.classList.remove("has-file", "is-selected");
}

async function resolveCipherSource(kind) {
    const encrypting = kind === "encrypt";
    const textInput = encrypting ? encryptTextInput : decryptTextInput;
    const state = cipherState[kind];
    const typedText = textInput?.value ?? "";

    if (typedText.trim()) {
        return { content: typedText, filename: null };
    }
    if (!state.file) {
        throw new Error(encrypting
            ? "Enter plaintext or select a plaintext .txt file."
            : "Enter ciphertext or select an encrypted .txt file.");
    }

    const content = await state.file.text();
    if (!content.trim()) {
        throw new Error(encrypting
            ? "The selected plaintext file is empty."
            : "The selected encrypted file is empty.");
    }
    return { content, filename: state.file.name };
}

async function runEncrypt() {
    const state = cipherState.encrypt;
    if (state.busy) return;
    if (!hasCipherInput("encrypt")) {
        setError(encryptError, "Enter plaintext or select a plaintext .txt file.");
        setStatus(encryptStatus, "Plaintext required", "error");
        return;
    }

    let shift;
    try {
        shift = validateCipherShift(encryptCipherKey);
    } catch (error) {
        state.operation += 1;
        resetEncryptResult();
        setError(encryptError, error.message);
        setStatus(encryptStatus, "Invalid shift", "error");
        return;
    }

    const operation = ++state.operation;
    resetEncryptResult();
    setCipherBusy("encrypt", true);
    setStatus(encryptStatus, "Encrypting...", "primary");

    try {
        const source = await resolveCipherSource("encrypt");
        const payload = { plaintext: source.content, shift };
        if (source.filename) payload.filename = source.filename;
        const result = await postJson("/api/encrypt-text", payload);
        if (operation !== state.operation) return;

        state.result = result;
        if (encryptOutput) encryptOutput.textContent = result.ciphertext;
        if (copyCiphertextButton) copyCiphertextButton.disabled = false;
        if (downloadEncryptedButton) downloadEncryptedButton.disabled = false;
        if (useInDecryptButton) useInDecryptButton.disabled = false;
        setStatus(encryptStatus, "Encryption complete", "success");
    } catch (error) {
        if (operation !== state.operation) return;
        setError(encryptError, error.message);
        setStatus(encryptStatus, "Encryption failed", "error");
    } finally {
        if (operation === state.operation) setCipherBusy("encrypt", false);
    }
}

async function runDecrypt() {
    const state = cipherState.decrypt;
    if (state.busy) return;
    if (!hasCipherInput("decrypt")) {
        setError(decryptError, "Enter ciphertext or select an encrypted .txt file.");
        setStatus(decryptStatus, "Ciphertext required", "error");
        return;
    }

    let shift;
    try {
        shift = validateCipherShift(decryptCipherKey);
    } catch (error) {
        state.operation += 1;
        resetDecryptResult();
        setError(decryptError, error.message);
        setStatus(decryptStatus, "Invalid shift", "error");
        return;
    }

    const operation = ++state.operation;
    resetDecryptResult();
    setCipherBusy("decrypt", true);
    setStatus(decryptStatus, "Decrypting...", "primary");

    try {
        const source = await resolveCipherSource("decrypt");
        const payload = { ciphertext: source.content, shift };
        if (source.filename) payload.filename = source.filename;
        const result = await postJson("/api/decrypt-text", payload);
        if (operation !== state.operation) return;

        state.result = result;
        if (decryptOutput) decryptOutput.textContent = result.decrypted_message;
        if (copyDecryptedButton) copyDecryptedButton.disabled = false;
        if (downloadDecryptedButton) downloadDecryptedButton.disabled = false;
        setStatus(decryptStatus, "Decryption complete", "success");
    } catch (error) {
        if (operation !== state.operation) return;
        setError(decryptError, error.message);
        setStatus(decryptStatus, "Decryption failed", "error");
    } finally {
        if (operation === state.operation) setCipherBusy("decrypt", false);
    }
}

function useCiphertextInDecrypt() {
    const result = cipherState.encrypt.result;
    if (!result?.ciphertext || !decryptTextInput || !decryptCipherKey) return;

    cipherState.decrypt.operation += 1;
    clearSelectedCipherFile("decrypt");
    decryptTextInput.value = result.ciphertext;
    decryptCipherKey.value = String(result.shift);
    updateRangeFill(decryptCipherKey, decryptCipherKeyValue);
    resetDecryptResult();
    syncCipherActionState("decrypt");
    setError(decryptError);
    setStatus(decryptStatus, "Ciphertext ready - press Decrypt", "primary");
    showDecryptPanel();
    decryptTextInput.focus();
}

function handleCipherTextInput(kind) {
    const encrypting = kind === "encrypt";
    const status = encrypting ? encryptStatus : decryptStatus;
    const errorBox = encrypting ? encryptError : decryptError;
    cipherState[kind].operation += 1;
    if (encrypting) resetEncryptResult();
    else resetDecryptResult();
    syncCipherActionState(kind);
    setError(errorBox);
    setStatus(
        status,
        hasCipherInput(kind)
            ? `Input changed - press ${encrypting ? "Encrypt" : "Decrypt"}`
            : "Awaiting input",
        "neutral",
    );
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
        setBusy(false);
        if (systemEngineStatus) systemEngineStatus.textContent = "Engine online";
        drawScene();
    } catch (error) {
        graph = null;
        setBusy(false);
        if (systemEngineStatus) systemEngineStatus.textContent = "Engine offline";
        if (algorithmLog) algorithmLog.textContent = `[ERR] ${error.message}`;
        if (runStatus) {
            runStatus.textContent = "Offline";
            runStatus.className = "badge badge-neutral";
        }
    }
}

function downloadTextFile(filename, content) {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}

function downloadRoute() {
    if (!currentResult || !currentRequest || !mapCiphertextResult?.ciphertext || routeDownloadBusy) return;
    const filename = `route_${currentRequest.start}_${currentRequest.goal}.txt`;
    routeDownloadBusy = true;
    if (downloadRouteButton) {
        downloadRouteButton.disabled = true;
        downloadRouteButton.classList.add("is-loading");
        downloadRouteButton.setAttribute("aria-busy", "true");
    }
    try {
        downloadTextFile(filename, `Ciphertext:\n${mapCiphertextResult.ciphertext}`);
        setStatus(routeExportStatus, "Encrypted route downloaded", "success");
        appendLog(`Downloaded ciphertext file: ${filename}`);
    } catch (error) {
        setStatus(routeExportStatus, `Download failed: ${error.message}`, "error");
    } finally {
        // Keep the button locked until the next task so a double-click cannot
        // create two downloads. It becomes available again if the result remains.
        window.setTimeout(() => {
            routeDownloadBusy = false;
            if (downloadRouteButton) {
                downloadRouteButton.classList.remove("is-loading");
                downloadRouteButton.setAttribute("aria-busy", "false");
                downloadRouteButton.disabled = !currentResult || !currentRequest || !mapCiphertextResult?.ciphertext;
            }
        }, 0);
    }
}

function sourceBaseName(file, fallback) {
    if (!file?.name) return fallback;
    return file.name.replace(/\.txt$/i, "") || fallback;
}

function downloadEncryptedResult() {
    const state = cipherState.encrypt;
    const result = state.result;
    if (!result?.ciphertext || state.downloadBusy) return;
    const baseName = sourceBaseName(state.file, "message");
    state.downloadBusy = true;
    if (downloadEncryptedButton) {
        downloadEncryptedButton.disabled = true;
        downloadEncryptedButton.classList.add("is-loading");
        downloadEncryptedButton.setAttribute("aria-busy", "true");
    }
    try {
        downloadTextFile(`${baseName}_encrypted.txt`, `Ciphertext:\n${result.ciphertext}`);
        setStatus(encryptStatus, "Encrypted file downloaded", "success");
    } catch (error) {
        setError(encryptError, `Download failed: ${error.message}`);
        setStatus(encryptStatus, "Download failed", "error");
    } finally {
        window.setTimeout(() => {
            state.downloadBusy = false;
            if (downloadEncryptedButton) {
                downloadEncryptedButton.disabled = !state.result?.ciphertext;
                downloadEncryptedButton.classList.remove("is-loading");
                downloadEncryptedButton.setAttribute("aria-busy", "false");
            }
        }, 0);
    }
}

function downloadDecryptedResult() {
    const state = cipherState.decrypt;
    const result = state.result;
    if (!result?.decrypted_message || state.downloadBusy) return;
    const baseName = sourceBaseName(state.file, "message").replace(/_encrypted$/i, "");
    state.downloadBusy = true;
    if (downloadDecryptedButton) {
        downloadDecryptedButton.disabled = true;
        downloadDecryptedButton.classList.add("is-loading");
        downloadDecryptedButton.setAttribute("aria-busy", "true");
    }
    try {
        downloadTextFile(`${baseName}_decrypted.txt`, `Plaintext:\n${result.decrypted_message}`);
        setStatus(decryptStatus, "Decrypted file downloaded", "success");
    } catch (error) {
        setError(decryptError, `Download failed: ${error.message}`);
        setStatus(decryptStatus, "Download failed", "error");
    } finally {
        window.setTimeout(() => {
            state.downloadBusy = false;
            if (downloadDecryptedButton) {
                downloadDecryptedButton.disabled = !state.result?.decrypted_message;
                downloadDecryptedButton.classList.remove("is-loading");
                downloadDecryptedButton.setAttribute("aria-busy", "false");
            }
        }, 0);
    }
}

async function copyText(text) {
    if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return;
    }
    const temporaryInput = document.createElement("textarea");
    temporaryInput.value = text;
    temporaryInput.setAttribute("readonly", "");
    temporaryInput.style.position = "fixed";
    temporaryInput.style.opacity = "0";
    document.body.appendChild(temporaryInput);
    temporaryInput.select();
    const copied = document.execCommand("copy");
    temporaryInput.remove();
    if (!copied) throw new Error("Clipboard permission was denied.");
}

async function copyCiphertext() {
    const result = cipherState.encrypt.result;
    if (!result?.ciphertext) return;
    try {
        await copyText(result.ciphertext);
        setStatus(encryptStatus, "Ciphertext copied", "success");
    } catch (error) {
        setError(encryptError, `Copy failed: ${error.message}`);
    }
}

async function copyDecryptedResult() {
    const result = cipherState.decrypt.result;
    if (!result?.decrypted_message) return;
    try {
        await copyText(result.decrypted_message);
        setStatus(decryptStatus, "Result copied", "success");
    } catch (error) {
        setError(decryptError, `Copy failed: ${error.message}`);
    }
}

function activateTab(activeTab, inactiveTab, activePanel, inactivePanel) {
    activeTab?.classList.add("active");
    activeTab?.setAttribute("aria-selected", "true");
    activeTab?.setAttribute("tabindex", "0");
    inactiveTab?.classList.remove("active");
    inactiveTab?.setAttribute("aria-selected", "false");
    inactiveTab?.setAttribute("tabindex", "-1");
    if (activePanel) {
        activePanel.classList.add("active");
        activePanel.hidden = false;
        activePanel.classList.remove("hidden");
    }
    if (inactivePanel) {
        inactivePanel.classList.remove("active");
        inactivePanel.hidden = true;
        inactivePanel.classList.add("hidden");
    }
}

function deactivatePage(tab, panel) {
    tab?.classList.remove("active");
    tab?.setAttribute("aria-selected", "false");
    tab?.setAttribute("tabindex", "-1");
    if (panel) {
        panel.classList.remove("active");
        panel.hidden = true;
        panel.classList.add("hidden");
    }
}

function showMapPage() {
    activateTab(mapPageTab, cipherPageTab, mapPagePanel, cipherPagePanel);
    deactivatePage(textPageTab, textPagePanel);
    window.requestAnimationFrame(drawScene);
}

function showCipherPage() {
    activateTab(cipherPageTab, mapPageTab, cipherPagePanel, mapPagePanel);
    deactivatePage(textPageTab, textPagePanel);
}

function showTextPage() {
    activateTab(textPageTab, mapPageTab, textPagePanel, mapPagePanel);
    deactivatePage(cipherPageTab, cipherPagePanel);
}

function showEncryptPanel() {
    activateTab(encryptTab, decryptTab, encryptPanel, decryptPanel);
}

function showDecryptPanel() {
    activateTab(decryptTab, encryptTab, decryptPanel, encryptPanel);
}

function bindTabKeyboard(tabs, activate) {
    tabs.forEach((tab, index) => {
        tab?.addEventListener("keydown", (event) => {
            let nextIndex = null;
            if (event.key === "ArrowRight" || event.key === "ArrowDown") {
                nextIndex = (index + 1) % tabs.length;
            } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
                nextIndex = (index - 1 + tabs.length) % tabs.length;
            } else if (event.key === "Home") {
                nextIndex = 0;
            } else if (event.key === "End") {
                nextIndex = tabs.length - 1;
            }

            if (nextIndex === null || !tabs[nextIndex]) return;
            event.preventDefault();
            tabs[nextIndex].focus();
            activate(nextIndex);
        });
    });
}

// Event Listeners
runButton?.addEventListener("click", runAStar);
resetButton?.addEventListener("click", () => reset());
downloadRouteButton?.addEventListener("click", downloadRoute);
mapPageTab?.addEventListener("click", showMapPage);
cipherPageTab?.addEventListener("click", showCipherPage);
textPageTab?.addEventListener("click", showTextPage);
encryptTab?.addEventListener("click", showEncryptPanel);
decryptTab?.addEventListener("click", showDecryptPanel);
bindTabKeyboard([mapPageTab, cipherPageTab, textPageTab], (index) => {
    if (index === 0) showMapPage();
    else if (index === 1) showCipherPage();
    else showTextPage();
});
bindTabKeyboard([encryptTab, decryptTab], (index) => {
    if (index === 0) showEncryptPanel();
    else showDecryptPanel();
});

encryptFileInput?.addEventListener("change", () => selectCipherFile("encrypt"));
decryptFileInput?.addEventListener("change", () => selectCipherFile("decrypt"));
encryptTextInput?.addEventListener("input", () => handleCipherTextInput("encrypt"));
decryptTextInput?.addEventListener("input", () => handleCipherTextInput("decrypt"));
encryptButton?.addEventListener("click", runEncrypt);
decryptButton?.addEventListener("click", runDecrypt);
copyCiphertextButton?.addEventListener("click", copyCiphertext);
copyDecryptedButton?.addEventListener("click", copyDecryptedResult);
downloadEncryptedButton?.addEventListener("click", downloadEncryptedResult);
downloadDecryptedButton?.addEventListener("click", downloadDecryptedResult);
useInDecryptButton?.addEventListener("click", useCiphertextInDecrypt);

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
    select.addEventListener("change", () => reset());
});

mapCipherKey?.addEventListener("input", () => {
    updateRangeFill(mapCipherKey, mapCipherKeyValue);
    if (!currentResult) return;

    mapEncryptionOperation += 1;
    mapCiphertextResult = null;
    if (routeSerializedOutput) {
        routeSerializedOutput.textContent = "Shift changed. Release the slider to encrypt the route.";
    }
    if (downloadRouteButton) downloadRouteButton.disabled = true;
    setStatus(routeExportStatus, "Shift changed", "neutral");
});

mapCipherKey?.addEventListener("change", () => {
    if (currentResult && currentRequest && !mapEncryptionBusy) {
        void refreshMapEncryption(currentResult, animationToken);
    }
});

encryptCipherKey?.addEventListener("input", () => {
    cipherState.encrypt.operation += 1;
    updateRangeFill(encryptCipherKey, encryptCipherKeyValue);
    resetEncryptResult();
    syncCipherActionState("encrypt");
    setStatus(encryptStatus, hasCipherInput("encrypt") ? "Shift changed - press Encrypt" : "Awaiting input", "neutral");
});

decryptCipherKey?.addEventListener("input", () => {
    cipherState.decrypt.operation += 1;
    updateRangeFill(decryptCipherKey, decryptCipherKeyValue);
    resetDecryptResult();
    syncCipherActionState("decrypt");
    setStatus(decryptStatus, hasCipherInput("decrypt") ? "Shift changed - press Decrypt" : "Awaiting input", "neutral");
});

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
showMapPage();
showEncryptPanel();
if (new URLSearchParams(window.location.search).get("workspace") === "text") {
    showTextPage();
}
updateRangeFill(mapCipherKey, mapCipherKeyValue);
updateRangeFill(encryptCipherKey, encryptCipherKeyValue);
updateRangeFill(decryptCipherKey, decryptCipherKeyValue);
resetEncryptResult();
resetDecryptResult();
loadGraph();
