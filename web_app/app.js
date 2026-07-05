const riskColors = {
  Low: "#2c7bb6",
  Guarded: "#abd9e9",
  Moderate: "#ffffbf",
  High: "#fdae61",
  Severe: "#d7191c",
};

const state = {
  map: null,
  data: null,
  riskLayer: null,
  susceptibilityLayer: null,
  boundaryLayer: null,
  rainfallLayer: null,
  landslideLayer: null,
  currentWindow: "combined",
};

const formatNumber = (value, digits = 1) =>
  Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });

const setText = (id, value) => {
  document.getElementById(id).textContent = value;
};

function assetUrl(path) {
  const version = encodeURIComponent(state.data?.generatedAt || Date.now());
  return `${path}?v=${version}`;
}

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Could not load ${path}`);
  }
  return response.json();
}

function initMap() {
  state.map = L.map("map", {
    zoomControl: true,
    preferCanvas: true,
  });

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(state.map);
}

function addBoundary(boundary) {
  state.boundaryLayer = L.geoJSON(boundary, {
    style: {
      color: "#111827",
      weight: 1.5,
      fillOpacity: 0,
    },
  }).addTo(state.map);
  state.map.fitBounds(state.boundaryLayer.getBounds(), { padding: [18, 18] });
}

function makeImageLayer(path, bounds, opacity = 0.88) {
  return L.imageOverlay(assetUrl(path), bounds, {
    opacity,
    interactive: false,
  });
}

function addRasterLayers() {
  state.riskLayer = makeImageLayer(
    state.data.overlays.risk[state.currentWindow],
    state.data.bounds.risk,
    0.9,
  ).addTo(state.map);

  state.susceptibilityLayer = makeImageLayer(
    state.data.overlays.susceptibility,
    state.data.bounds.susceptibility,
    0.84,
  );
}

function markerPopup(properties) {
  return `
    <strong>Rainfall sample point</strong>
    Current: ${formatNumber(properties.current_rain_mm)} mm<br>
    1h: ${formatNumber(properties.rain_1h_mm)} mm<br>
    3h: ${formatNumber(properties.rain_3h_mm)} mm<br>
    24h: ${formatNumber(properties.rain_24h_mm)} mm<br>
    72h: ${formatNumber(properties.rain_72h_mm)} mm<br>
    Trigger: ${formatNumber(properties.rainfall_trigger_score, 3)}
  `;
}

function addPointLayers(rainfall, landslides) {
  state.rainfallLayer = L.geoJSON(rainfall, {
    pointToLayer: (feature, latlng) => {
      const trigger = Number(feature.properties.rainfall_trigger_score || 0);
      return L.circleMarker(latlng, {
        radius: 4 + trigger * 5,
        color: "#0f172a",
        weight: 1,
        fillColor: "#38bdf8",
        fillOpacity: 0.9,
        pane: "markerPane",
      });
    },
    onEachFeature: (feature, layer) => {
      layer.bindPopup(markerPopup(feature.properties));
    },
  }).addTo(state.map);

  state.landslideLayer = L.geoJSON(landslides, {
    pointToLayer: (_feature, latlng) =>
      L.circleMarker(latlng, {
        radius: 2.8,
        color: "#ffffff",
        weight: 0.8,
        fillColor: "#111827",
        fillOpacity: 0.76,
        pane: "markerPane",
      }),
    onEachFeature: (feature, layer) => {
      layer.bindPopup(`
        <strong>Landslide inventory point</strong>
        Sample ID: ${feature.properties.sample_id}<br>
        Lon: ${Number(feature.properties.longitude).toFixed(5)}<br>
        Lat: ${Number(feature.properties.latitude).toFixed(5)}
      `);
    },
  });
}

function updateCards() {
  const cards = state.data.cards;
  setText("maxRain1h", `${formatNumber(cards.maxRain1h)} mm`);
  setText("maxRain24h", `${formatNumber(cards.maxRain24h)} mm`);
  setText("highSevereArea", `${formatNumber(cards.highSevereArea)}%`);
  setText("severeArea", `${formatNumber(cards.severeArea)}%`);
  setText(
    "updatedAt",
    `Rainfall timestamp: ${state.data.rainfallLatestTime} | Generated: ${state.data.generatedAt}`,
  );
}

function updateBars() {
  const container = document.getElementById("riskBars");
  container.innerHTML = "";
  state.data.summaries.risk.forEach((row) => {
    const wrapper = document.createElement("div");
    wrapper.className = "bar-row";
    wrapper.innerHTML = `
      <span>${row.risk_label}</span>
      <span class="bar-track">
        <span class="bar-fill" style="width:${row.area_percent}%; background:${riskColors[row.risk_label]}"></span>
      </span>
      <span>${formatNumber(row.area_percent)}%</span>
    `;
    container.appendChild(wrapper);
  });
}

function refreshRiskLayer(windowName) {
  state.currentWindow = windowName;
  if (state.riskLayer && state.map.hasLayer(state.riskLayer)) {
    state.map.removeLayer(state.riskLayer);
  }
  state.riskLayer = makeImageLayer(
    state.data.overlays.risk[windowName],
    state.data.bounds.risk,
    0.9,
  );
  if (document.getElementById("riskToggle").checked) {
    state.riskLayer.addTo(state.map);
  }
}

async function refreshLiveData() {
  const button = document.getElementById("refreshButton");
  const status = document.getElementById("refreshStatus");
  button.disabled = true;
  button.textContent = "Refreshing...";
  status.textContent = "Fetching Open-Meteo rainfall and rebuilding warning layers.";

  try {
    const response = await fetch("/api/refresh", { method: "POST" });
    if (!response.ok) {
      let message = "Refresh endpoint is not available.";
      try {
        const payload = await response.json();
        message = payload.error || message;
      } catch (_error) {
        message = await response.text();
      }
      throw new Error(message);
    }
    status.textContent = "Refresh complete. Reloading dashboard.";
    window.location.reload();
  } catch (error) {
    status.textContent =
      `Live refresh failed: ${error.message}`;
    button.disabled = false;
    button.textContent = "Refresh rainfall and risk map";
  }
}

function bindControls() {
  document.querySelectorAll("#windowControl button").forEach((button) => {
    button.addEventListener("click", () => {
      document
        .querySelectorAll("#windowControl button")
        .forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      refreshRiskLayer(button.dataset.window);
    });
  });

  const toggleLayer = (checkboxId, layerGetter) => {
    const checkbox = document.getElementById(checkboxId);
    checkbox.addEventListener("change", () => {
      const layer = layerGetter();
      if (checkbox.checked) {
        layer.addTo(state.map);
      } else {
        state.map.removeLayer(layer);
      }
    });
  };

  toggleLayer("riskToggle", () => state.riskLayer);
  toggleLayer("susceptibilityToggle", () => state.susceptibilityLayer);
  toggleLayer("rainfallToggle", () => state.rainfallLayer);
  toggleLayer("landslideToggle", () => state.landslideLayer);

  document
    .getElementById("refreshButton")
    .addEventListener("click", refreshLiveData);
}

async function start() {
  try {
    const [appData, boundary, rainfall, landslides] = await Promise.all([
      loadJson("data/app-data.json"),
      loadJson("data/boundary.geojson"),
      loadJson("data/rainfall_points.geojson"),
      loadJson("data/landslide_points.geojson"),
    ]);

    state.data = appData;
    initMap();
    addRasterLayers();
    addBoundary(boundary);
    addPointLayers(rainfall, landslides);
    updateCards();
    updateBars();
    bindControls();
  } catch (error) {
    console.error(error);
    document.getElementById("updatedAt").textContent =
      "Could not load dashboard data. Run python -m src.export_web_app first.";
  }
}

start();
