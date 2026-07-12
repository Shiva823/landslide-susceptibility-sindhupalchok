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
  rainfallMarkers: new Map(),
  currentWindow: "combined",
};

const formatNumber = (value, digits = 1) =>
  Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });

const formatPercent = (value) => {
  const numeric = Number(value || 0);
  const digits = numeric > 0 && numeric < 1 ? 2 : 1;
  return `${formatNumber(numeric, digits)}%`;
};

const setText = (id, value) => {
  document.getElementById(id).textContent = value;
};

function assetUrl(path) {
  const version = encodeURIComponent(state.data?.generatedAt || Date.now());
  return `${path}?v=${version}`;
}

async function loadJson(path) {
  const separator = path.includes("?") ? "&" : "?";
  const response = await fetch(`${path}${separator}v=${Date.now()}`, {
    cache: "no-store",
  });
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
  rainfall.features.forEach((feature, index) => {
    feature.properties.sample_index = index + 1;
  });
  state.rainfallMarkers.clear();

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
      state.rainfallMarkers.set(feature.properties.sample_index, layer);
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
  setText("highSevereArea", formatPercent(cards.highSevereArea));
  setText("severeArea", formatPercent(cards.severeArea));
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
      <span>${formatPercent(row.area_percent)}</span>
    `;
    container.appendChild(wrapper);
  });
}

function warningDetails() {
  const cards = state.data.cards;
  const highSevere = Number(cards.highSevereArea || 0);
  const severe = Number(cards.severeArea || 0);
  const trigger = Number(cards.maxTrigger || 0);
  const rain72h = Number(cards.maxRain72h || 0);

  if (severe >= 1 || highSevere >= 12 || trigger >= 0.6) {
    return {
      label: "Elevated",
      title: "High attention needed",
      color: "#d7191c",
      reason:
        `The current rainfall trigger reaches ${formatNumber(trigger, 2)} and ${formatPercent(highSevere)} of the district is in high or severe dynamic warning.`,
    };
  }
  if (highSevere >= 5 || trigger >= 0.3 || rain72h >= 60) {
    return {
      label: "Watch",
      title: "Rainfall is lifting risk in susceptible terrain",
      color: "#f97316",
      reason:
        `The strongest 72h rainfall total is ${formatNumber(rain72h)} mm. The map should be inspected around high-susceptibility slopes touched by the wetter sample points.`,
    };
  }
  return {
    label: "Normal",
    title: "No broad warning spike in this run",
    color: "#0f766e",
    reason:
      `Recent rainfall is present, but only ${formatPercent(highSevere)} of the district is currently mapped as high or severe dynamic warning.`,
  };
}

function updateWarningPanel() {
  const details = warningDetails();
  const badge = document.getElementById("warningBadge");
  badge.textContent = details.label;
  badge.style.background = details.color;
  setText("warningTitle", details.title);
  setText("warningReason", details.reason);
}

function updateRainfallBars() {
  const cards = state.data.cards;
  const rows = [
    ["1h", cards.maxRain1h, 20],
    ["3h", cards.maxRain3h, 40],
    ["24h", cards.maxRain24h, 100],
    ["72h", cards.maxRain72h, 180],
  ];
  const container = document.getElementById("rainfallBars");
  container.innerHTML = "";

  rows.forEach(([label, value, scale]) => {
    const width = Math.min(100, (Number(value || 0) / scale) * 100);
    const row = document.createElement("div");
    row.className = "rain-row";
    row.innerHTML = `
      <span>${label}</span>
      <span class="rain-track">
        <span class="rain-fill" style="width:${width}%; background:#0f766e"></span>
      </span>
      <span>${formatNumber(value)} mm</span>
    `;
    container.appendChild(row);
  });
}

function updateValidationSignal() {
  const susceptibility = state.data.summaries.susceptibility || [];
  const highClasses = susceptibility.filter((row) =>
    ["High", "Very High"].includes(row.class_label),
  );
  const area = highClasses.reduce(
    (total, row) => total + Number(row.area_percent || 0),
    0,
  );
  const landslides = highClasses.reduce(
    (total, row) => total + Number(row.landslide_percent || 0),
    0,
  );

  setText("validationArea", formatPercent(area));
  setText("validationSlides", formatPercent(landslides));
  setText(
    "validationText",
    ` A smaller share of terrain contains most recorded landslides, so the susceptibility map is concentrating past failures into the highest classes.`,
  );
}

function updateHotspots() {
  const container = document.getElementById("hotspotList");
  const points = [...(state.data.summaries.rainfall || [])]
    .map((point, index) => ({ ...point, sample_index: index + 1 }))
    .sort(
      (a, b) =>
        Number(b.rainfall_trigger_score || 0) -
        Number(a.rainfall_trigger_score || 0),
    )
    .slice(0, 4);

  container.innerHTML = "";
  points.forEach((point, rank) => {
    const button = document.createElement("button");
    button.className = "hotspot-button";
    button.type = "button";
    button.innerHTML = `
      <strong>Sample ${point.sample_index} · ${formatNumber(point.rain_72h_mm)} mm / 72h</strong>
      <span>#${rank + 1}</span>
      <small>${formatNumber(point.rain_24h_mm)} mm / 24h · trigger ${formatNumber(point.rainfall_trigger_score, 2)}</small>
    `;
    button.addEventListener("click", () => {
      const layer = state.rainfallMarkers.get(point.sample_index);
      const latlng = L.latLng(point.latitude, point.longitude);
      state.map.setView(latlng, Math.max(state.map.getZoom(), 12), {
        animate: true,
      });
      if (layer) {
        if (!state.map.hasLayer(state.rainfallLayer)) {
          document.getElementById("rainfallToggle").checked = true;
          state.rainfallLayer.addTo(state.map);
        }
        layer.openPopup();
      }
    });
    container.appendChild(button);
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

function coordinateText(latlng) {
  return `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`;
}

function locationPopupContent(result, latlng) {
  const place = result.place || "Sindhupalchok District";
  const rows = [
    result.localName ? `Local place: ${result.localName}` : null,
    result.municipality ? `Municipality: ${result.municipality}` : null,
    result.district ? `District: ${result.district}` : null,
    result.province ? `Province: ${result.province}` : null,
  ].filter(Boolean);

  return `
    <strong>${place}</strong>
    ${rows.length ? `${rows.join("<br>")}<br>` : ""}
    Lat/Lon: ${coordinateText(latlng)}
    <span class="popup-muted">${result.displayName || "Place name from map lookup"}</span>
  `;
}

async function lookupPlace(latlng) {
  const params = new URLSearchParams({
    lat: latlng.lat,
    lon: latlng.lng,
  });
  const response = await fetch(`/api/reverse-geocode?${params.toString()}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Place lookup unavailable");
  }
  return response.json();
}

function bindMapClickLookup() {
  state.map.on("click", async (event) => {
    const popup = L.popup()
      .setLatLng(event.latlng)
      .setContent(`
        <strong>Looking up place...</strong>
        Lat/Lon: ${coordinateText(event.latlng)}
      `)
      .openOn(state.map);

    try {
      const result = await lookupPlace(event.latlng);
      popup.setContent(locationPopupContent(result, event.latlng));
    } catch (_error) {
      popup.setContent(`
        <strong>Sindhupalchok District</strong>
        Lat/Lon: ${coordinateText(event.latlng)}<br>
        <span class="popup-muted">Place lookup unavailable for this click.</span>
      `);
    }
  });
}

async function reloadDashboardInPlace() {
  try {
    const [appData, rainfall] = await Promise.all([
      loadJson("data/app-data.json"),
      loadJson("data/rainfall_points.geojson"),
    ]);
    state.data = appData;

    // Update raster overlays
    if (state.riskLayer && state.map.hasLayer(state.riskLayer)) {
      state.map.removeLayer(state.riskLayer);
    }
    state.riskLayer = makeImageLayer(
      state.data.overlays.risk[state.currentWindow],
      state.data.bounds.risk,
      0.9,
    );
    if (document.getElementById("riskToggle").checked) {
      state.riskLayer.addTo(state.map);
    }

    // Update rainfall markers
    if (state.rainfallLayer && state.map.hasLayer(state.rainfallLayer)) {
      state.map.removeLayer(state.rainfallLayer);
    }
    rainfall.features.forEach((feature, index) => {
      feature.properties.sample_index = index + 1;
    });
    state.rainfallMarkers.clear();
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
        state.rainfallMarkers.set(feature.properties.sample_index, layer);
        layer.bindPopup(markerPopup(feature.properties));
      },
    });
    if (document.getElementById("rainfallToggle").checked) {
      state.rainfallLayer.addTo(state.map);
    }

    // Refresh all sidebar panels
    updateCards();
    updateBars();
    updateWarningPanel();
    updateRainfallBars();
    updateValidationSignal();
    updateHotspots();
  } catch (err) {
    console.error("In-place reload failed:", err);
  }
}

async function refreshLiveData() {
  const button = document.getElementById("refreshButton");
  const status = document.getElementById("refreshStatus");
  const progressWrap = document.getElementById("refreshProgressWrap");
  const progressBar = document.getElementById("refreshProgressBar");
  const progressPct = document.getElementById("refreshProgressPct");
  const progressTimer = document.getElementById("refreshProgressTimer");

  button.disabled = true;
  button.textContent = "Refreshing…";
  progressWrap.style.display = "block";
  progressBar.style.width = "0%";
  progressPct.textContent = "0%";

  const startTime = Date.now();
  let timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const m = Math.floor(elapsed / 60).toString().padStart(2, "0");
    const s = (elapsed % 60).toString().padStart(2, "0");
    progressTimer.textContent = `${m}:${s}`;
  }, 1000);

  try {
    await new Promise((resolve, reject) => {
      const es = new EventSource("/api/refresh/stream");
      let resolved = false;

      es.onmessage = (event) => {
        let data;
        try { data = JSON.parse(event.data); } catch { return; }

        if (data.pct === -1) {
          es.close();
          reject(new Error(data.error || "Refresh failed on server."));
          return;
        }

        const pct = Math.max(0, Math.min(100, data.pct));
        progressBar.style.width = `${pct}%`;
        progressPct.textContent = `${pct}%`;
        status.textContent = data.msg || "";

        if (pct >= 100) {
          resolved = true;
          es.close();
          resolve();
        }
      };

      // onerror fires on normal stream close too — only reject if we
      // haven't already resolved successfully.
      es.onerror = () => {
        es.close();
        if (!resolved) {
          reject(new Error("Refresh stream closed before completion."));
        }
      };
    });

    // Success — reload data in-place, no navigation
    clearInterval(timerInterval);
    progressBar.style.width = "100%";
    progressPct.textContent = "100%";
    status.textContent = "Applying new data to dashboard…";
    await reloadDashboardInPlace();
    status.textContent = "✓ Dashboard updated with latest rainfall data.";

    setTimeout(() => {
      progressWrap.style.display = "none";
    }, 3000);

  } catch (error) {
    clearInterval(timerInterval);
    progressWrap.style.display = "none";
    status.textContent = `Refresh failed: ${error.message}`;
  } finally {
    clearInterval(timerInterval);
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

  // Landing Page transitions
  const landingPage = document.getElementById("landingPage");
  document.getElementById("exploreMapBtn").addEventListener("click", () => {
    landingPage.classList.add("hidden");
    if (state.map) {
      setTimeout(() => {
        state.map.invalidateSize();
      }, 400);
    }
  });

  document.getElementById("backToHomeBtn").addEventListener("click", () => {
    landingPage.classList.remove("hidden");
  });

  // Sidebar collapse toggle
  document.getElementById("sidebarToggleBtn").addEventListener("click", () => {
    const appShell = document.querySelector(".app-shell");
    appShell.classList.toggle("sidebar-collapsed");
    // Give the CSS transition time to finish before telling Leaflet to resize
    setTimeout(() => {
      if (state.map) state.map.invalidateSize();
    }, 320);
  });
  // Layers panel click-toggle (stays open until clicked again or outside)
  const layersBtn = document.getElementById("layersBtn");
  const layersControl = layersBtn.closest(".floating-layers-control");
  layersBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = layersControl.classList.toggle("open");
    layersBtn.classList.toggle("open", isOpen);
  });
  document.addEventListener("click", (e) => {
    if (!layersControl.contains(e.target)) {
      layersControl.classList.remove("open");
      layersBtn.classList.remove("open");
    }
  });
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
    updateWarningPanel();
    updateRainfallBars();
    updateValidationSignal();
    updateHotspots();
    bindControls();
    bindMapClickLookup();
  } catch (error) {
    console.error(error);
    document.getElementById("updatedAt").textContent =
      "Could not load dashboard data. Run python -m src.export_web_app first.";
  }
}

start();
