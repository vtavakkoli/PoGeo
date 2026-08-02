const map = L.map("map", { zoomControl: true }).setView([48.2085, 16.3731], 12);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

let resultLayer = L.geoJSON([], {
  pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
    radius: 7,
    weight: 2,
    color: "#07111c",
    fillColor: "#31d6a2",
    fillOpacity: 0.95,
  }),
  onEachFeature: (feature, layer) => {
    const properties = feature.properties || {};
    const title = properties.name || `Feature ${feature.id ?? ""}`;
    const category = properties.category || "feature";
    const district = properties.district ? ` · district ${properties.district}` : "";
    layer.bindPopup(`<strong>${escapeHtml(title)}</strong><span>${escapeHtml(category)}${escapeHtml(district)}</span>`);
  },
}).addTo(map);

const conversation = document.querySelector("#conversation");
const form = document.querySelector("#chat-form");
const question = document.querySelector("#question");
const send = document.querySelector("#send");
const toolOutput = document.querySelector("#tool-output");
const featureCount = document.querySelector("#feature-count");
const statusBadge = document.querySelector("#ai-status");
const modelName = document.querySelector("#model-name");
const history = [];
let allFeatures = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function addMessage(role, text, error = false) {
  const article = document.createElement("article");
  article.className = `message ${role === "user" ? "user-message" : "assistant-message"}${error ? " error-message" : ""}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "Y" : "P";

  const body = document.createElement("div");
  const strong = document.createElement("strong");
  strong.textContent = role === "user" ? "You" : "PoGeo";
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  body.append(strong, paragraph);
  article.append(avatar, body);
  conversation.append(article);
  conversation.scrollTop = conversation.scrollHeight;
}

function drawFeatures(featureCollection, fit = true) {
  resultLayer.clearLayers();
  resultLayer.addData(featureCollection || { type: "FeatureCollection", features: [] });
  const count = featureCollection?.features?.length || 0;
  featureCount.textContent = `${count} feature${count === 1 ? "" : "s"} on map`;
  if (fit && count > 0) {
    const bounds = resultLayer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.15), { maxZoom: 15 });
  }
}

async function loadAllPlaces() {
  try {
    const response = await fetch("/collections/places/items?limit=1000");
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    allFeatures = await response.json();
    drawFeatures(allFeatures);
  } catch (error) {
    featureCount.textContent = `Could not load features: ${error.message}`;
  }
}

async function checkAi() {
  try {
    const response = await fetch("/api/ai/status");
    const data = await response.json();
    modelName.textContent = data.model || "Ollama";
    if (data.available && data.installed) {
      statusBadge.textContent = "Ollama ready";
      statusBadge.className = "status status-online";
    } else if (data.available) {
      statusBadge.textContent = "Model is downloading";
      statusBadge.className = "status status-waiting";
    } else {
      throw new Error(data.error || "Ollama unavailable");
    }
  } catch {
    statusBadge.textContent = "Ollama offline";
    statusBadge.className = "status status-offline";
  }
}

function mapContext() {
  const bounds = map.getBounds();
  return {
    bbox: [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()],
    zoom: map.getZoom(),
    visible_collections: ["places"],
  };
}

async function ask(text) {
  addMessage("user", text);
  history.push({ role: "user", content: text });
  send.disabled = true;
  send.firstElementChild.textContent = "Analysing…";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        history: history.slice(-10, -1),
        map_context: mapContext(),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed with ${response.status}`);

    addMessage("assistant", data.answer);
    history.push({ role: "assistant", content: data.answer });
    toolOutput.textContent = data.tool_executions?.length
      ? JSON.stringify(data.tool_executions, null, 2)
      : "The model answered without a database tool call.";
    if (data.feature_collection) drawFeatures(data.feature_collection);
  } catch (error) {
    addMessage("assistant", `${error.message}. Start the AI profile with: docker compose --profile ai up --build`, true);
  } finally {
    send.disabled = false;
    send.firstElementChild.textContent = "Ask PoGeo";
    question.focus();
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = question.value.trim();
  if (!text) return;
  question.value = "";
  await ask(text);
});

question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    question.value = button.textContent.trim();
    form.requestSubmit();
  });
});

document.querySelector("#show-all").addEventListener("click", () => {
  if (allFeatures) drawFeatures(allFeatures);
});

await Promise.all([loadAllPlaces(), checkAi()]);
