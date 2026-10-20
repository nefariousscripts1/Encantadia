"use strict";

const textEncoder = new TextEncoder();
const MAX_FILE_BYTES = 1_000_000;
const MAX_BATCH_BYTES = 2_000_000;
const MAX_DATASETS = 25;
const PREVIEW_LIMIT = 20_000;

const SAMPLE_TEXT = `Algorithm analysis connects theoretical complexity with observable behavior.
Knuth–Morris–Pratt searches text without retreating in the source. Huffman coding uses frequent symbols efficiently. Dynamic programming solves the 0/1 Knapsack selection problem, and Randomized QuickSort ranks results with randomly chosen pivots.

Algorithms are precise procedures. Studying algorithms means checking correctness, edge cases, resource use, and reproducibility. This sample repeats algorithms so pattern matching has more than one result.`;

const labState = {
    datasets: [],
    activeId: null,
    nextId: 1,
    priorities: new Map(),
    huffmanBase64: null,
};

const byId = (id) => document.getElementById(id);
const algorithmTabs = [...document.querySelectorAll(".lab-algorithm-tab")];

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function byteLength(text) {
    return textEncoder.encode(text).length;
}

function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KiB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MiB`;
}

function formatMs(value) {
    if (value === undefined || value === null) return "Not Available";
    return `${Number(value).toFixed(3)} ms`;
}

function setMessage(message, isError = false) {
    const target = byId("datasetMessage");
    target.textContent = message;
    target.classList.toggle("is-error", isError);
}

function setLabStatus(message, state = "ready") {
    const target = byId("labStatus");
    target.textContent = message;
    target.dataset.state = state;
}

function activeDataset() {
    return labState.datasets.find((dataset) => dataset.id === labState.activeId) || null;
}

function metricMarkup(metrics) {
    return metrics.map(([label, value]) => `<div class="metric"><span>${escapeHtml(label)}</span><strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong></div>`).join("");
}

function tableMarkup(headers, rows, rowClass = () => "") {
    if (!rows.length) return '<p class="empty-state">No rows to display.</p>';
    return `<table class="data-table"><thead><tr>${headers.map((header) => `<th scope="col">${escapeHtml(header)}</th>`).join("")}</tr></thead><tbody>${rows.map((row, index) => `<tr class="${escapeHtml(rowClass(row, index))}">${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

async function apiRequest(url, body) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({ error: "The server returned an unreadable response." }));
    if (!response.ok) throw new Error(payload.error || `Request failed with status ${response.status}.`);
    return payload;
}

async function runOperation(button, label, operation) {
    const originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = label;
    setLabStatus("Processing…", "loading");
    try {
        await operation();
        setLabStatus("Completed", "success");
    } catch (error) {
        setLabStatus("Error", "error");
        setMessage(error.message, true);
    } finally {
        button.disabled = false;
        button.textContent = originalLabel;
    }
}

function switchAlgorithm(tab) {
    algorithmTabs.forEach((candidate) => {
        const active = candidate === tab;
        candidate.classList.toggle("is-active", active);
        candidate.setAttribute("aria-selected", String(active));
        candidate.tabIndex = active ? 0 : -1;
        byId(candidate.dataset.algorithm).hidden = !active;
    });
}

function enableTabKeyboard(tabs, activate) {
    tabs.forEach((tab, index) => {
        tab.addEventListener("keydown", (event) => {
            let nextIndex = null;
            if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
            if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
            if (event.key === "Home") nextIndex = 0;
            if (event.key === "End") nextIndex = tabs.length - 1;
            if (nextIndex === null) return;
            event.preventDefault();
            activate(tabs[nextIndex]);
            tabs[nextIndex].focus();
        });
    });
}

function updateEditorStats() {
    const text = byId("textEditor").value;
    byId("editorStats").textContent = `${text.length.toLocaleString()} characters · ${formatBytes(byteLength(text))}`;
}

function makeDataset(name, text, originalBytes = null) {
    return {
        id: labState.nextId++,
        name,
        text,
        byteSize: byteLength(text),
        originalBytes: originalBytes ?? byteLength(text),
    };
}

function selectDataset(id) {
    const dataset = labState.datasets.find((candidate) => candidate.id === id);
    if (!dataset) return;
    labState.activeId = id;
    byId("datasetName").value = dataset.name;
    byId("textEditor").value = dataset.text;
    byId("saveDatasetButton").textContent = "Replace Dataset";
    byId("activeDatasetSummary").textContent = `${dataset.name} · ${dataset.text.length.toLocaleString()} characters · ${formatBytes(dataset.byteSize)}`;
    updateEditorStats();
    renderDatasets();
}

function removeDataset(id) {
    labState.datasets = labState.datasets.filter((dataset) => dataset.id !== id);
    labState.priorities.delete(id);
    if (labState.activeId === id) {
        labState.activeId = labState.datasets[0]?.id ?? null;
        if (labState.activeId) selectDataset(labState.activeId);
        else {
            byId("activeDatasetSummary").textContent = "Select a dataset to begin analysis.";
            byId("saveDatasetButton").textContent = "Add Dataset";
        }
    }
    renderDatasets();
    renderKnapsackTable();
}

function renderDatasets() {
    const container = byId("datasetList");
    byId("datasetCount").textContent = `${labState.datasets.length} dataset${labState.datasets.length === 1 ? "" : "s"}`;
    if (!labState.datasets.length) {
        container.innerHTML = '<p class="empty-state">Add text, load the sample, or upload UTF-8 files.</p>';
        return;
    }
    container.replaceChildren();
    labState.datasets.forEach((dataset) => {
        const row = document.createElement("div");
        row.className = "dataset-entry";
        const select = document.createElement("button");
        select.type = "button";
        select.className = `dataset-item${dataset.id === labState.activeId ? " is-active" : ""}`;
        select.setAttribute("aria-pressed", String(dataset.id === labState.activeId));
        const preview = dataset.text.replaceAll(/\s+/g, " ").slice(0, 90) || "Empty text";
        select.innerHTML = `<strong>${escapeHtml(dataset.name)}</strong><small>${formatBytes(dataset.byteSize)}</small><span class="dataset-preview">${escapeHtml(preview)}</span>`;
        select.addEventListener("click", () => selectDataset(dataset.id));
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "remove-dataset";
        remove.textContent = "Remove";
        remove.setAttribute("aria-label", `Remove ${dataset.name}`);
        remove.addEventListener("click", () => removeDataset(dataset.id));
        row.append(select, remove);
        container.append(row);
    });
}

function addOrReplaceEditorDataset() {
    const name = byId("datasetName").value.trim();
    const text = byId("textEditor").value;
    if (!name) return setMessage("Enter a dataset name before saving.", true);
    if (!name.toLowerCase().endsWith(".txt")) return setMessage("Dataset names must use the .txt extension.", true);
    const size = byteLength(text);
    if (!text) return setMessage("Enter or paste text before saving the dataset.", true);
    if (size > MAX_FILE_BYTES) return setMessage(`The dataset exceeds the ${formatBytes(MAX_FILE_BYTES)} limit.`, true);

    const selected = activeDataset();
    const matching = labState.datasets.find((dataset) => dataset.name.toLowerCase() === name.toLowerCase());
    if (selected && selected.name.toLowerCase() === name.toLowerCase()) {
        selected.text = text;
        selected.byteSize = size;
        selected.originalBytes = size;
        setMessage(`Replaced ${name}.`);
        selectDataset(selected.id);
    } else if (matching) {
        matching.text = text;
        matching.byteSize = size;
        matching.originalBytes = size;
        setMessage(`Replaced the existing dataset named ${name}.`);
        selectDataset(matching.id);
    } else {
        if (labState.datasets.length >= MAX_DATASETS) return setMessage(`Only ${MAX_DATASETS} datasets can be loaded at once.`, true);
        const dataset = makeDataset(name, text);
        labState.datasets.push(dataset);
        labState.priorities.set(dataset.id, 1);
        setMessage(`Added ${name}.`);
        selectDataset(dataset.id);
    }
    renderKnapsackTable();
}

function loadSample() {
    byId("datasetName").value = "algorithm-sample.txt";
    byId("textEditor").value = SAMPLE_TEXT;
    updateEditorStats();
    addOrReplaceEditorDataset();
}

async function uploadFiles(files) {
    if (!files.length) return;
    if (labState.datasets.length + files.length > MAX_DATASETS) return setMessage(`The collection is limited to ${MAX_DATASETS} datasets.`, true);
    const totalSize = [...files].reduce((total, file) => total + file.size, 0);
    if (totalSize > MAX_BATCH_BYTES) return setMessage(`The selected batch exceeds ${formatBytes(MAX_BATCH_BYTES)}.`, true);

    const added = [];
    for (const file of files) {
        if (!file.name.toLowerCase().endsWith(".txt")) throw new Error(`${file.name} is not a .txt file.`);
        if (file.size > MAX_FILE_BYTES) throw new Error(`${file.name} exceeds ${formatBytes(MAX_FILE_BYTES)}.`);
        const bytes = new Uint8Array(await file.arrayBuffer());
        let text;
        try {
            text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
        } catch {
            throw new Error(`${file.name} is not valid UTF-8 text.`);
        }
        const existing = labState.datasets.find((dataset) => dataset.name.toLowerCase() === file.name.toLowerCase());
        if (existing) {
            existing.text = text;
            existing.byteSize = byteLength(text);
            existing.originalBytes = file.size;
            added.push(existing);
        } else {
            const dataset = makeDataset(file.name, text, file.size);
            labState.datasets.push(dataset);
            labState.priorities.set(dataset.id, 1);
            added.push(dataset);
        }
    }
    if (added.length) selectDataset(added[added.length - 1].id);
    renderDatasets();
    renderKnapsackTable();
    setMessage(`Loaded ${added.length} UTF-8 file${added.length === 1 ? "" : "s"}.`);
}

function clearDatasets() {
    labState.datasets = [];
    labState.activeId = null;
    labState.priorities.clear();
    labState.huffmanBase64 = null;
    byId("textEditor").value = "";
    byId("datasetName").value = "manual-input.txt";
    byId("activeDatasetSummary").textContent = "Select a dataset to begin analysis.";
    byId("saveDatasetButton").textContent = "Add Dataset";
    byId("downloadHuffmanButton").disabled = true;
    byId("decompressHuffmanButton").disabled = true;
    updateEditorStats();
    renderDatasets();
    renderKnapsackTable();
    setMessage("Dataset collection cleared.");
}

function requireDataset() {
    const dataset = activeDataset();
    if (!dataset) throw new Error("Select or add a dataset first.");
    return dataset;
}

function renderMatchPreview(text, pattern, matches) {
    const preview = byId("kmpPreview");
    const shownText = text.slice(0, PREVIEW_LIMIT);
    const covered = new Uint8Array(shownText.length);
    matches.forEach((start) => {
        for (let index = start; index < Math.min(start + pattern.length, shownText.length); index += 1) covered[index] = 1;
    });
    preview.replaceChildren();
    let index = 0;
    while (index < shownText.length) {
        const highlighted = covered[index] === 1;
        let end = index + 1;
        while (end < shownText.length && (covered[end] === 1) === highlighted) end += 1;
        const node = highlighted ? document.createElement("mark") : document.createTextNode(shownText.slice(index, end));
        if (highlighted) node.textContent = shownText.slice(index, end);
        preview.append(node);
        index = end;
    }
    if (text.length > PREVIEW_LIMIT) preview.append(document.createTextNode(`\n\n[Preview limited to ${PREVIEW_LIMIT.toLocaleString()} characters to keep the interface responsive.]`));
    preview.classList.remove("empty-state");
}

async function runKmp() {
    const button = byId("runKmpButton");
    await runOperation(button, "Searching…", async () => {
        const dataset = requireDataset();
        const pattern = byId("kmpPattern").value;
        if (!pattern) throw new Error("Enter a non-empty search pattern.");
        const result = await apiRequest("/api/text/kmp", { text: dataset.text, pattern });
        byId("kmpMetrics").innerHTML = metricMarkup([
            ["Matches", result.match_count.toLocaleString()], ["Execution", formatMs(result.execution_time_ms)],
            ["Text length", result.text_length.toLocaleString()], ["Pattern length", result.pattern_length.toLocaleString()],
        ]);
        const displayed = result.matches.length > 5000 ? result.matches.slice(0, 5000) : result.matches;
        byId("kmpPositions").textContent = result.match_count ? `Starts: ${displayed.join(", ")}${displayed.length < result.matches.length ? ` · first ${displayed.length.toLocaleString()} shown` : ""}` : "No matches found";
        renderMatchPreview(dataset.text, pattern, result.matches);
        byId("lpsTable").classList.remove("empty-state");
        byId("lpsTable").innerHTML = tableMarkup(
            ["Pattern index", "Character", "LPS value"],
            [...pattern].map((character, index) => [String(index), `<code>${escapeHtml(character)}</code>`, String(result.lps[index])]),
        );
        setMessage(`KMP searched ${dataset.name} without using a built-in substring search.`);
    });
}

async function runHuffman() {
    const button = byId("runHuffmanButton");
    await runOperation(button, "Compressing…", async () => {
        const dataset = requireDataset();
        const result = await apiRequest("/api/text/huffman/compress", { text: dataset.text });
        labState.huffmanBase64 = result.data_base64;
        byId("downloadHuffmanButton").disabled = false;
        byId("decompressHuffmanButton").disabled = false;
        byId("huffmanMetrics").innerHTML = metricMarkup([
            ["Original", formatBytes(result.original_size_bytes)], ["Payload", formatBytes(result.payload_size_bytes)],
            ["Metadata", formatBytes(result.metadata_size_bytes)], ["Total .gch", formatBytes(result.compressed_size_bytes)],
            ["Ratio", result.compression_ratio === null ? "Not Available" : `${result.compression_ratio.toFixed(3)} : 1`],
            ["Space savings", `${result.space_savings_percent.toFixed(2)}%`],
            ["Compress", formatMs(result.execution_time_ms)], ["Decompress", formatMs(result.decompression_time_ms)],
        ]);
        const verification = byId("huffmanVerification");
        verification.textContent = result.verified ? "Verified: decompressed UTF-8 text exactly matches the original." : "Verification failed: decompressed text differs from the original.";
        verification.className = `verification-line ${result.verified ? "is-success" : "is-error"}`;
        byId("huffmanTable").classList.remove("empty-state");
        byId("huffmanTable").innerHTML = tableMarkup(
            ["Byte", "Symbol", "Frequency", "Huffman code"],
            result.frequency_table.map((row) => [String(row.byte), `<code>${escapeHtml(row.symbol)}</code>`, row.frequency.toLocaleString(), `<code>${escapeHtml(row.code)}</code>`]),
        );
        setMessage(`Compressed ${dataset.name} into a ${formatBytes(result.compressed_size_bytes)} binary artifact.`);
    });
}

async function downloadHuffman() {
    const dataset = requireDataset();
    const response = await fetch("/api/text/huffman/download", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: dataset.text }),
    });
    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || "Unable to create the Huffman download.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${dataset.name.replace(/\.txt$/i, "")}.gch`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

async function decompressAgain() {
    if (!labState.huffmanBase64) throw new Error("Compress a dataset before decompressing it.");
    const result = await apiRequest("/api/text/huffman/decompress", { data_base64: labState.huffmanBase64 });
    const matches = result.text === requireDataset().text;
    const verification = byId("huffmanVerification");
    verification.textContent = `${matches ? "Verified again" : "Mismatch"}: server decompression took ${formatMs(result.execution_time_ms)}.`;
    verification.className = `verification-line ${matches ? "is-success" : "is-error"}`;
}

function renderKnapsackTable(selectedNames = new Set()) {
    const target = byId("knapsackTable");
    if (!labState.datasets.length) {
        target.className = "table-wrap empty-state";
        target.textContent = "Add datasets to assign priorities and processing costs.";
        return;
    }
    target.className = "table-wrap";
    target.innerHTML = tableMarkup(
        ["Dataset", "UTF-8 size", "Cost", "Priority", "Selected"],
        labState.datasets.map((dataset) => {
            const priority = labState.priorities.get(dataset.id) ?? 1;
            return [escapeHtml(dataset.name), formatBytes(dataset.byteSize), `${Math.ceil(dataset.byteSize / 1024)} unit(s)`, `<input class="priority-input" type="number" min="0" max="1000000" step="0.1" value="${escapeHtml(priority)}" data-priority-id="${dataset.id}" aria-label="Priority for ${escapeHtml(dataset.name)}">`, selectedNames.has(dataset.name) ? "Yes" : "—"];
        }),
        (_row, index) => selectedNames.has(labState.datasets[index].name) ? "selected-row" : "",
    );
    target.querySelectorAll("[data-priority-id]").forEach((input) => {
        input.addEventListener("input", () => labState.priorities.set(Number(input.dataset.priorityId), Number(input.value)));
    });
}

async function runKnapsack() {
    const button = byId("runKnapsackButton");
    await runOperation(button, "Optimizing…", async () => {
        if (!labState.datasets.length) throw new Error("Add at least one dataset before optimizing.");
        const budget = Number(byId("knapsackBudget").value);
        const datasets = labState.datasets.map((dataset) => ({
            name: dataset.name, byte_size: dataset.byteSize, priority: labState.priorities.get(dataset.id) ?? 1,
        }));
        const result = await apiRequest("/api/text/knapsack", { datasets, budget });
        const selectedNames = new Set(result.selected_items.map((item) => item.name));
        byId("knapsackMetrics").innerHTML = metricMarkup([
            ["Selected", result.selected_items.length.toLocaleString()], ["Total cost", `${result.total_cost} / ${result.budget}`],
            ["Optimized score", String(result.total_score)], ["Execution", formatMs(result.execution_time_ms)],
        ]);
        byId("knapsackSelectionNote").textContent = selectedNames.size ? `Selected: ${[...selectedNames].join(", ")}` : "No dataset fits the budget";
        renderKnapsackTable(selectedNames);
        setMessage("0/1 dynamic programming completed with reproducible input-order tie behavior.");
    });
}

async function runRanking() {
    const button = byId("runRankingButton");
    await runOperation(button, "Ranking…", async () => {
        if (!labState.datasets.length) throw new Error("Add at least one dataset before ranking.");
        const pattern = byId("rankingPattern").value;
        if (!pattern) throw new Error("Enter a non-empty search pattern.");
        const seedValue = byId("randomSeed").value.trim();
        const seed = seedValue === "" ? null : Number(seedValue);
        if (seed !== null && !Number.isInteger(seed)) throw new Error("The optional random seed must be an integer.");
        const result = await apiRequest("/api/text/rank", {
            pattern, seed, datasets: labState.datasets.map(({ name, text }) => ({ name, text })),
        });
        byId("rankingMetrics").innerHTML = metricMarkup([
            ["Files ranked", result.ranked_results.length.toLocaleString()], ["KMP total", formatMs(result.kmp_execution_time_ms)],
            ["QuickSort", formatMs(result.execution_time_ms)], ["Seed", result.seed === null ? "Random" : String(result.seed)],
        ]);
        byId("rankingTable").classList.remove("empty-state");
        byId("rankingTable").innerHTML = tableMarkup(
            ["Rank", "Dataset", "Matches", "Starting positions"],
            result.ranked_results.map((row, index) => [String(index + 1), escapeHtml(row.name), row.match_count.toLocaleString(), `<code>${escapeHtml(row.matches.join(", ") || "None")}</code>`]),
        );
        setMessage("KMP results ranked by manually implemented Randomized QuickSort.");
    });
}

function renderBenchmarkChart(rows) {
    const target = byId("benchmarkChart");
    const maximum = Math.max(...rows.map((row) => row.execution_time_ms), 0.001);
    target.className = "benchmark-chart";
    target.innerHTML = rows.map((row) => {
        const height = Math.max(2, (row.execution_time_ms / maximum) * 145);
        const shortName = row.algorithm.replace(" String Matching", "").replace(" Coding", "").replace("Randomized ", "").replace("0/1 ", "");
        return `<div class="benchmark-bar-group" title="${escapeHtml(`${row.algorithm}: ${formatMs(row.execution_time_ms)}`)}"><div class="benchmark-bar" style="height:${height.toFixed(2)}px"></div><small>${escapeHtml(shortName)}<br>${escapeHtml(row.dataset_category)}</small></div>`;
    }).join("");
}

async function runBenchmarks() {
    const button = byId("runBenchmarkButton");
    await runOperation(button, "Benchmarking…", async () => {
        const sizes = byId("benchmarkSizes").value.split(",").map((part) => Number(part.trim())).filter((value) => !Number.isNaN(value));
        const result = await apiRequest("/api/text/benchmark", { sizes });
        renderBenchmarkChart(result.rows);
        byId("benchmarkMethod").textContent = result.timing_method;
        byId("benchmarkTable").classList.remove("empty-state");
        byId("benchmarkTable").innerHTML = tableMarkup(
            ["Dataset", "Algorithm", "Input", "Time", "Peak memory", "Time complexity", "Space complexity", "Status / result"],
            result.rows.map((row) => [
                escapeHtml(row.dataset_category), escapeHtml(row.algorithm), Number(row.input_size).toLocaleString(), formatMs(row.execution_time_ms),
                row.measured_memory_bytes === null ? "Not Available" : formatBytes(row.measured_memory_bytes), escapeHtml(row.time_complexity),
                escapeHtml(row.space_complexity), `${escapeHtml(row.status)}<br><code>${escapeHtml(row.result)}</code>`,
            ]),
        );
        setMessage("Benchmarks completed on the backend; interface rendering time was excluded.");
    });
}

algorithmTabs.forEach((tab) => tab.addEventListener("click", () => switchAlgorithm(tab)));
enableTabKeyboard(algorithmTabs, switchAlgorithm);
byId("textEditor").addEventListener("input", updateEditorStats);
byId("saveDatasetButton").addEventListener("click", addOrReplaceEditorDataset);
byId("sampleDatasetButton").addEventListener("click", loadSample);
byId("clearDatasetsButton").addEventListener("click", clearDatasets);
byId("textFileInput").addEventListener("change", async (event) => {
    try { await uploadFiles(event.target.files); } catch (error) { setMessage(error.message, true); }
    event.target.value = "";
});
byId("runKmpButton").addEventListener("click", runKmp);
byId("runHuffmanButton").addEventListener("click", runHuffman);
byId("downloadHuffmanButton").addEventListener("click", () => runOperation(byId("downloadHuffmanButton"), "Preparing…", downloadHuffman));
byId("decompressHuffmanButton").addEventListener("click", () => runOperation(byId("decompressHuffmanButton"), "Decoding…", decompressAgain));
byId("runKnapsackButton").addEventListener("click", runKnapsack);
byId("runRankingButton").addEventListener("click", runRanking);
byId("runBenchmarkButton").addEventListener("click", runBenchmarks);

updateEditorStats();
renderDatasets();
renderKnapsackTable();

