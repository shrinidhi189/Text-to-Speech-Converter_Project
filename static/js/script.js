const textInput = document.getElementById("textInput");
const charCount = document.getElementById("charCount");
const voiceSelect = document.getElementById("voiceSelect");
const rateSlider = document.getElementById("rateSlider");
const rateValue = document.getElementById("rateValue");
const convertBtn = document.getElementById("convertBtn");
const downloadBtn = document.getElementById("downloadBtn");
const clearBtn = document.getElementById("clearBtn");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const player = document.getElementById("player");
const historyBody = document.getElementById("historyBody");
const micBadge = document.getElementById("micBadge");

let lastAudioUrl = null;

// ---------------- init ----------------
document.addEventListener("DOMContentLoaded", () => {
  loadVoices();
  loadHistory();
});

textInput.addEventListener("input", () => {
  charCount.textContent = textInput.value.length;
});

rateSlider.addEventListener("input", () => {
  const v = parseInt(rateSlider.value, 10);
  rateValue.textContent = (v > 0 ? "+" : "") + v + "%";
});

// ---------------- status helper ----------------
function setStatus(kind, message) {
  statusText.textContent = message;
  statusDot.className = "status-dot" + (kind === "busy" ? " busy" : kind === "error" ? " error" : "");
}

// ---------------- voices ----------------
async function loadVoices() {
  try {
    const res = await fetch("/api/voices");
    const voices = await res.json();
    voiceSelect.innerHTML = "";

    // Group by locale (e.g. "en-IN") so a long catalog stays browsable.
    const groups = {};
    voices.forEach(v => {
      const key = v.locale || "Other";
      if (!groups[key]) groups[key] = [];
      groups[key].push(v);
    });

    Object.keys(groups).sort().forEach(locale => {
      const optgroup = document.createElement("optgroup");
      optgroup.label = locale;
      groups[locale].forEach(v => {
        const opt = document.createElement("option");
        opt.value = v.id;
        opt.textContent = v.label;
        optgroup.appendChild(opt);
      });
      voiceSelect.appendChild(optgroup);
    });
  } catch (err) {
    setStatus("error", "Could not load voice list");
  }
}

// ---------------- convert ----------------
convertBtn.addEventListener("click", async () => {
  const text = textInput.value.trim();
  if (!text) {
    setStatus("error", "Enter some text first");
    return;
  }

  convertBtn.disabled = true;
  micBadge.classList.add("speaking");
  setStatus("busy", "Generating speech...");

  try {
    const res = await fetch("/api/convert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        voice: voiceSelect.value,
        rate: parseInt(rateSlider.value, 10),
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      setStatus("error", data.error || "Conversion failed");
      return;
    }

    lastAudioUrl = data.audio_url;
    downloadBtn.disabled = false;
    player.src = lastAudioUrl;
    player.play();
    setStatus("ready", "Playing audio");
    prependHistoryRow(data.entry);
  } catch (err) {
    setStatus("error", "Network error - is the server running?");
  } finally {
    convertBtn.disabled = false;
    micBadge.classList.remove("speaking");
  }
});

player.addEventListener("ended", () => setStatus("ready", "Ready"));

// ---------------- download / clear ----------------
downloadBtn.addEventListener("click", () => {
  if (!lastAudioUrl) return;
  const a = document.createElement("a");
  a.href = lastAudioUrl;
  a.download = "speech.mp3";
  a.click();
});

clearBtn.addEventListener("click", () => {
  textInput.value = "";
  charCount.textContent = "0";
  player.pause();
  player.src = "";
  downloadBtn.disabled = true;
  lastAudioUrl = null;
  setStatus("ready", "Ready");
});

// ---------------- history ----------------
async function loadHistory() {
  try {
    const res = await fetch("/api/history");
    const history = await res.json();
    renderHistory(history);
  } catch (err) {
    // silent fail, table stays as-is
  }
}

function renderHistory(history) {
  historyBody.innerHTML = "";
  if (!history.length) {
    historyBody.innerHTML = '<tr class="empty-row"><td colspan="6">No conversions yet — your history will show up here.</td></tr>';
    return;
  }
  history.forEach((entry, idx) => {
    historyBody.appendChild(buildRow(entry, history.length - idx));
  });
}

function prependHistoryRow(entry) {
  const emptyRow = historyBody.querySelector(".empty-row");
  if (emptyRow) emptyRow.remove();

  const rows = historyBody.querySelectorAll("tr");
  const nextNo = rows.length + 1;
  const row = buildRow(entry, nextNo);
  historyBody.prepend(row);
}

function buildRow(entry, no) {
  const tr = document.createElement("tr");
  tr.dataset.id = entry.id;

  const audioUrl = `/static/audio/${entry.filename}`;

  tr.innerHTML = `
    <td>${no}</td>
    <td class="text-cell" title="${escapeHtml(entry.text)}">${escapeHtml(entry.text)}</td>
    <td class="voice-cell">${escapeHtml(entry.voice)}</td>
    <td><button class="row-icon-btn play" title="Play">&#9654;</button></td>
    <td><button class="row-icon-btn download" title="Download">&#8681;</button></td>
    <td><button class="row-icon-btn delete" title="Delete">&#128465;</button></td>
  `;

  tr.querySelector(".play").addEventListener("click", () => {
    player.src = audioUrl;
    player.play();
    setStatus("ready", "Playing audio");
  });

  tr.querySelector(".download").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = audioUrl;
    a.download = "speech.mp3";
    a.click();
  });

  tr.querySelector(".delete").addEventListener("click", async () => {
    try {
      await fetch(`/api/history/${entry.id}`, { method: "DELETE" });
      tr.remove();
      renumberRows();
      if (!historyBody.querySelector("tr")) {
        historyBody.innerHTML = '<tr class="empty-row"><td colspan="6">No conversions yet — your history will show up here.</td></tr>';
      }
    } catch (err) {
      setStatus("error", "Could not delete entry");
    }
  });

  return tr;
}

function renumberRows() {
  const rows = historyBody.querySelectorAll("tr:not(.empty-row)");
  const total = rows.length;
  rows.forEach((row, idx) => {
    row.children[0].textContent = total - idx;
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
