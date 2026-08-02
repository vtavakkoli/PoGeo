(() => {
  'use strict';

  const state = {
    map: null,
    conversationId: null,
    activeCollection: null,
  };

  const elements = {
    healthText: document.querySelector('#healthText'),
    healthPill: document.querySelector('.status-pill'),
    collectionList: document.querySelector('#collectionList'),
    refreshCatalog: document.querySelector('#refreshCatalog'),
    chatForm: document.querySelector('#chatForm'),
    chatInput: document.querySelector('#chatInput'),
    sendButton: document.querySelector('#sendButton'),
    conversation: document.querySelector('#conversation'),
    suggestions: document.querySelector('#suggestions'),
    toolTrace: document.querySelector('#toolTrace'),
    resultCount: document.querySelector('#resultCount'),
    activeLayer: document.querySelector('#activeLayer'),
    modelChip: document.querySelector('#modelChip'),
  };

  window.addEventListener('DOMContentLoaded', init);

  async function init() {
    await waitForMapLibre();
    initMap();
    bindEvents();
    await Promise.all([checkHealth(), loadCatalog()]);
  }

  function waitForMapLibre() {
    return new Promise((resolve, reject) => {
      let attempts = 0;
      const timer = setInterval(() => {
        attempts += 1;
        if (window.maplibregl) {
          clearInterval(timer);
          resolve();
        } else if (attempts > 100) {
          clearInterval(timer);
          reject(new Error('MapLibre could not be loaded'));
        }
      }, 50);
    });
  }

  function initMap() {
    state.map = new maplibregl.Map({
      container: 'map',
      center: [16.3725, 48.2084],
      zoom: 11.4,
      attributionControl: false,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [
          { id: 'background', type: 'background', paint: { 'background-color': '#07111f' } },
          {
            id: 'osm', type: 'raster', source: 'osm',
            paint: { 'raster-opacity': 0.55, 'raster-saturation': -0.65, 'raster-contrast': 0.18, 'raster-brightness-max': 0.68 },
          },
        ],
      },
    });
    state.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    state.map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left');
  }

  function bindEvents() {
    elements.refreshCatalog.addEventListener('click', loadCatalog);
    elements.chatForm.addEventListener('submit', (event) => {
      event.preventDefault();
      const message = elements.chatInput.value.trim();
      if (message) ask(message);
    });
    elements.suggestions.addEventListener('click', (event) => {
      const button = event.target.closest('button');
      if (button) ask(button.textContent.trim());
    });
  }

  async function checkHealth() {
    try {
      const response = await fetch('/health');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const health = await response.json();
      elements.healthText.textContent = 'PostGIS ready';
      elements.healthPill.classList.add('online');
      elements.modelChip.textContent = health.aiModel;
    } catch (error) {
      elements.healthText.textContent = 'Service unavailable';
      elements.healthPill.classList.add('offline');
      console.error(error);
    }
  }

  async function loadCatalog() {
    elements.collectionList.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
    try {
      const response = await fetch('/collections');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      elements.collectionList.innerHTML = '';
      payload.collections.forEach((collection) => {
        const card = document.createElement('button');
        card.type = 'button';
        card.className = 'collection-card';
        card.innerHTML = `
          <span class="collection-icon">⌖</span>
          <span><strong>${escapeHtml(collection.title)}</strong><small>${escapeHtml(collection.description)}</small></span>
          <code>${escapeHtml(collection.geometryType)}</code>`;
        card.addEventListener('click', () => loadCollection(collection.id, collection.title));
        elements.collectionList.append(card);
      });
    } catch (error) {
      elements.collectionList.innerHTML = `<div class="empty-state">Could not load catalog: ${escapeHtml(error.message)}</div>`;
    }
  }

  async function loadCollection(id, title) {
    try {
      const response = await fetch(`/collections/${encodeURIComponent(id)}/items?limit=200`);
      if (!response.ok) throw new Error(await responseText(response));
      const geojson = await response.json();
      renderGeoJson(geojson, title);
      addAssistantMessage(`Loaded ${geojson.numberReturned ?? geojson.features?.length ?? 0} features from ${title}.`);
    } catch (error) {
      addAssistantMessage(`I could not load that collection: ${error.message}`, true);
    }
  }

  async function ask(message) {
    addUserMessage(message);
    elements.chatInput.value = '';
    elements.sendButton.disabled = true;
    const loading = addAssistantMessage('Running safe geospatial tools', false, true);

    try {
      const bounds = state.map.getBounds();
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          message,
          conversationId: state.conversationId,
          mapContext: {
            bbox: [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()],
            zoom: state.map.getZoom(),
            visibleCollections: state.activeCollection ? [state.activeCollection] : [],
          },
        }),
      });
      if (!response.ok) throw new Error(await responseText(response));
      const payload = await response.json();
      state.conversationId = payload.conversationId;
      loading.remove();
      addAssistantMessage(payload.answer);
      renderTrace(payload.toolCalls || []);
      if (payload.map) renderGeoJson(payload.map, 'AI query result');
      elements.modelChip.textContent = payload.model;
    } catch (error) {
      loading.remove();
      addAssistantMessage(`The AI request failed: ${error.message}. Ensure Ollama is running and the configured model is available.`, true);
    } finally {
      elements.sendButton.disabled = false;
      elements.chatInput.focus();
    }
  }

  function renderGeoJson(geojson, title) {
    const sourceId = 'pogeo-result';
    const pointLayer = 'pogeo-result-points';
    const lineLayer = 'pogeo-result-lines';
    const fillLayer = 'pogeo-result-fills';

    const update = () => {
      if (state.map.getSource(sourceId)) {
        state.map.getSource(sourceId).setData(geojson);
      } else {
        state.map.addSource(sourceId, { type: 'geojson', data: geojson });
        state.map.addLayer({
          id: fillLayer, type: 'fill', source: sourceId,
          filter: ['==', ['geometry-type'], 'Polygon'],
          paint: { 'fill-color': '#50e3b4', 'fill-opacity': 0.22, 'fill-outline-color': '#50e3b4' },
        });
        state.map.addLayer({
          id: lineLayer, type: 'line', source: sourceId,
          filter: ['==', ['geometry-type'], 'LineString'],
          paint: { 'line-color': '#6fc6ff', 'line-width': 4 },
        });
        state.map.addLayer({
          id: pointLayer, type: 'circle', source: sourceId,
          filter: ['==', ['geometry-type'], 'Point'],
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, 5, 15, 10],
            'circle-color': '#50e3b4', 'circle-stroke-color': '#07111f', 'circle-stroke-width': 2,
          },
        });
        state.map.on('click', pointLayer, showPopup);
        state.map.on('mouseenter', pointLayer, () => { state.map.getCanvas().style.cursor = 'pointer'; });
        state.map.on('mouseleave', pointLayer, () => { state.map.getCanvas().style.cursor = ''; });
      }
      fitToGeoJson(geojson);
    };

    if (state.map.isStyleLoaded()) update(); else state.map.once('load', update);
    const count = geojson.numberReturned ?? geojson.features?.length ?? 0;
    elements.resultCount.textContent = String(count);
    elements.activeLayer.textContent = title;
    state.activeCollection = title;
  }

  function showPopup(event) {
    const feature = event.features?.[0];
    if (!feature) return;
    const properties = feature.properties || {};
    const title = properties.name || `Feature ${feature.id ?? ''}`;
    const rows = Object.entries(properties)
      .filter(([key]) => key !== 'name')
      .slice(0, 6)
      .map(([key, value]) => `<div><small>${escapeHtml(key)}</small><br>${escapeHtml(String(value))}</div>`)
      .join('');
    new maplibregl.Popup({ offset: 10 })
      .setLngLat(feature.geometry.coordinates)
      .setHTML(`<strong>${escapeHtml(title)}</strong><div style="margin-top:8px;display:grid;gap:6px;font-size:11px;color:#aebdca">${rows}</div>`)
      .addTo(state.map);
  }

  function fitToGeoJson(geojson) {
    const coordinates = [];
    (geojson.features || []).forEach((feature) => collectCoordinates(feature.geometry?.coordinates, coordinates));
    if (!coordinates.length) return;
    const bounds = coordinates.reduce(
      (box, coordinate) => box.extend(coordinate),
      new maplibregl.LngLatBounds(coordinates[0], coordinates[0]),
    );
    state.map.fitBounds(bounds, { padding: 80, maxZoom: 14, duration: 900 });
  }

  function collectCoordinates(value, output) {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && typeof value[0] === 'number' && typeof value[1] === 'number') {
      output.push([value[0], value[1]]);
      return;
    }
    value.forEach((item) => collectCoordinates(item, output));
  }

  function renderTrace(records) {
    if (!records.length) {
      elements.toolTrace.className = 'empty-state';
      elements.toolTrace.textContent = 'The model answered without a tool call.';
      return;
    }
    elements.toolTrace.className = '';
    elements.toolTrace.innerHTML = records.map((record, index) => `
      <article class="trace-item">
        <header><span>${index + 1}. ${escapeHtml(record.name)}</span><span>validated</span></header>
        <p>${escapeHtml(record.summary)}</p>
        <pre>${escapeHtml(JSON.stringify(record.arguments, null, 2))}</pre>
      </article>`).join('');
  }

  function addUserMessage(text) {
    const article = document.createElement('article');
    article.className = 'message user';
    article.innerHTML = `<div><strong>You</strong><p>${escapeHtml(text)}</p></div><div class="avatar">Y</div>`;
    elements.conversation.append(article);
    scrollConversation();
  }

  function addAssistantMessage(text, isError = false, isLoading = false) {
    const article = document.createElement('article');
    article.className = `message assistant${isLoading ? ' loading' : ''}`;
    article.innerHTML = `<div class="avatar">P</div><div><strong>PoGeo</strong><p${isError ? ' style="color:#ff9bad"' : ''}>${escapeHtml(text)}</p></div>`;
    elements.conversation.append(article);
    scrollConversation();
    return article;
  }

  function scrollConversation() {
    elements.conversation.scrollTop = elements.conversation.scrollHeight;
  }

  async function responseText(response) {
    try {
      const payload = await response.json();
      return payload.message || payload.error || `HTTP ${response.status}`;
    } catch {
      return `HTTP ${response.status}`;
    }
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
    })[character]);
  }
})();
