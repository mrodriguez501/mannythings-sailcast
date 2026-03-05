/**
 * SailCast frontend: fetch /api/report and display location, recommendation,
 * 3-day forecast, hourly wind, alerts, tides. Refreshes every 30 minutes.
 */
const REPORT_URL = '/api/report';
const REFRESH_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes

const locationEl = document.getElementById('location');
const recommendationEl = document.getElementById('recommendation');
const lastFetchEl = document.getElementById('last-fetch');
const alertsListEl = document.getElementById('alerts-list');
const forecast3dayListEl = document.getElementById('forecast-3day-list');
const hourlyListEl = document.getElementById('hourly-list');
const hourCardsEl = document.getElementById('hour-cards');
const marineForecastEl = document.getElementById('marine-forecast');
const tideChartContainerEl = document.getElementById('tide-chart-container');
const tideChartMessageEl = document.getElementById('tide-chart-message');

/** Show loading / no-data / error message in a section container. */
function showSectionMessage(container, state, sectionName) {
  if (!container) return;
  const name = sectionName || 'Data';
  if (state === 'loading') {
    container.innerHTML = `<p class="section-message section-message--loading">Loading…</p>`;
    return;
  }
  if (state === 'no-data') {
    container.innerHTML = `<p class="section-message section-message--no-data">No data available.</p>`;
    return;
  }
  if (state === 'error') {
    const msg = typeof sectionName === 'string' ? sectionName : 'Error loading data.';
    container.innerHTML = `<p class="section-message section-message--error">${escapeHtml(msg)}</p>`;
    return;
  }
}

function setLoading() {
  if (locationEl) locationEl.textContent = '—';
  if (recommendationEl) recommendationEl.innerHTML = '<p class="loading">Loading…</p>';
  if (hourCardsEl) showSectionMessage(hourCardsEl, 'loading');
  if (alertsListEl) showSectionMessage(alertsListEl, 'loading');
  if (marineForecastEl) showSectionMessage(marineForecastEl, 'loading');
  if (hourlyListEl) showSectionMessage(hourlyListEl, 'loading');
  const tideCanvas = document.getElementById('tide-chart');
  if (tideCanvas) tideCanvas.style.display = 'none';
  if (tideChartMessageEl) {
    tideChartMessageEl.innerHTML = '<p class="section-message section-message--loading">Loading…</p>';
    tideChartMessageEl.style.display = '';
  }
  if (forecast3dayListEl) showSectionMessage(forecast3dayListEl, 'loading');
}

function formatTime(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
  } catch {
    return iso;
  }
}

function renderLocation(loc) {
  if (!locationEl || !loc) return;
  const { name, lat, lon } = loc;
  locationEl.textContent = `${name} (${lat}, ${lon})`;
}

function renderRecommendation(text) {
  if (!recommendationEl) return;
  recommendationEl.innerHTML = '';
  const p = document.createElement('p');
  p.textContent = text || 'No recommendation available.';
  recommendationEl.appendChild(p);
}

function escapeHtml(str) {
  if (str == null) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Build tidesByHour map for matching tide to hour key.
 */
function buildTidesByHour(tides) {
  const tidesByHour = {};
  if (!Array.isArray(tides)) return tidesByHour;
  for (const t of tides) {
    const tDate = new Date(t.t.replace(' ', 'T'));
    const key = hourKey(tDate);
    const label = (t.type === 'H') ? 'High' : (t.type === 'L') ? 'Low' : (t.type ?? '');
    tidesByHour[key] = `${label} ${t.v ?? ''} ft`.trim();
  }
  return tidesByHour;
}

/**
 * Render 24 hours forecast cards: date, conditions, wind (speed + direction), tide.
 */
function render24HourCards(hourly, tides) {
  if (!hourCardsEl) return;
  hourCardsEl.innerHTML = '';
  if (!Array.isArray(hourly) || hourly.length === 0) {
    showSectionMessage(hourCardsEl, 'no-data', '24 hours forecast');
    return;
  }
  const tidesByHour = buildTidesByHour(tides);
  const first24 = hourly.slice(0, 24);
  for (const p of first24) {
    const key = hourKey(p.startTime);
    const tideText = tidesByHour[key] ?? '—';
    const windStr = [p.windSpeed, p.windDirection].filter(Boolean).join(' ') || '—';
    const card = document.createElement('article');
    card.className = 'hour-card';
    card.innerHTML = `
      <header class="hour-card-date">${formatTime(p.startTime)}</header>
      <p class="hour-card-conditions">${escapeHtml(p.shortForecast ?? '—')}</p>
      <p class="hour-card-wind meta">Wind ${escapeHtml(windStr)}</p>
      <p class="hour-card-tide meta">${escapeHtml(tideText)}</p>
    `;
    hourCardsEl.appendChild(card);
  }
}

/**
 * Map NWS severity to USWDS alert variant (designsystem.digital.gov/components/alert/).
 */
function usaAlertVariant(severity) {
  const s = (severity || '').toLowerCase();
  if (s === 'extreme') return 'usa-alert--emergency';
  if (s === 'severe') return 'usa-alert--error';
  if (s === 'moderate') return 'usa-alert--warning';
  return 'usa-alert--info'; // Minor, Unknown, or missing
}

function renderAlerts(alerts) {
  if (!alertsListEl) return;
  alertsListEl.innerHTML = '';
  if (!Array.isArray(alerts) || alerts.length === 0) {
    showSectionMessage(alertsListEl, 'no-data');
    return;
  }
  for (const a of alerts) {
    const variant = usaAlertVariant(a.severity);
    const isCritical = (a.severity || '').toLowerCase() === 'extreme' || (a.severity || '').toLowerCase() === 'severe';
    const alertDiv = document.createElement('div');
    alertDiv.className = `usa-alert ${variant}`;
    if (isCritical) alertDiv.setAttribute('role', 'alert');
    const heading = a.event || 'Weather alert';
    const body = document.createElement('div');
    body.className = 'usa-alert__body';
    body.innerHTML = `
      <h4 class="usa-alert__heading">${escapeHtml(heading)}${a.severity ? ` (${escapeHtml(a.severity)})` : ''}</h4>
      ${a.headline ? `<p class="usa-alert__text">${escapeHtml(a.headline)}</p>` : ''}
      ${(a.onset || a.ends) ? `<p class="usa-alert__text meta">${[a.onset, a.ends].filter(Boolean).map(formatTime).join(' → ')}</p>` : ''}
    `;
    alertDiv.appendChild(body);
    alertsListEl.appendChild(alertDiv);
  }
}

/**
 * Render NWS marine zone forecast (ANZ535) in a USWDS-style alert box.
 * Source: marine.weather.gov/MapClick.php?TextType=1&zoneid=ANZ535 (text-only)
 */
function renderMarineForecast(marine) {
  if (!marineForecastEl) return;
  marineForecastEl.innerHTML = '';
  if (!marine || (!marine.forecast_text && !marine.error)) {
    showSectionMessage(marineForecastEl, 'no-data');
    return;
  }
  const text = marine.error || marine.forecast_text || '';
  const name = marine.name || marine.zone_id || 'ANZ535';
  const alertDiv = document.createElement('div');
  alertDiv.className = 'usa-alert usa-alert--info';
  alertDiv.setAttribute('role', 'region');
  alertDiv.setAttribute('aria-label', 'NWS Marine forecast');
  const body = document.createElement('div');
  body.className = 'usa-alert__body';
  const heading = document.createElement('h4');
  heading.className = 'usa-alert__heading';
  heading.textContent = `${marine.zone_id} – ${name}`;
  if (marine.url) {
    heading.appendChild(document.createTextNode(' '));
    const link = document.createElement('a');
    link.href = marine.url;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = 'View on NWS';
    heading.appendChild(link);
  }
  const para = document.createElement('p');
  para.className = 'usa-alert__text marine-forecast-text';
  para.textContent = text;
  body.appendChild(heading);
  body.appendChild(para);
  alertDiv.appendChild(body);
  marineForecastEl.appendChild(alertDiv);
}

function renderForecast3day(periods) {
  if (!forecast3dayListEl) return;
  forecast3dayListEl.innerHTML = '';
  if (!Array.isArray(periods) || periods.length === 0) {
    showSectionMessage(forecast3dayListEl, 'no-data');
    return;
  }
  const table = document.createElement('table');
  table.setAttribute('role', 'grid');
  table.innerHTML = `
    <thead><tr>
      <th>Period</th>
      <th>Temp</th>
      <th>Wind</th>
      <th>Conditions</th>
    </tr></thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector('tbody');
  for (const p of periods) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${p.name ?? '—'}</td>
      <td>${p.temp ?? '—'}°F</td>
      <td>${p.windSpeed ?? '—'} ${p.windDirection ?? ''}</td>
      <td>${p.shortForecast ?? '—'}</td>
    `;
    tbody.appendChild(tr);
  }
  forecast3dayListEl.appendChild(table);
}

/**
 * Build hour key (YYYY-MM-DD HH) in local time for matching tides to hourly rows.
 */
function hourKey(dateOrIso) {
  const d = typeof dateOrIso === 'string' ? new Date(dateOrIso) : dateOrIso;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const h = String(d.getHours()).padStart(2, '0');
  return `${y}-${m}-${day} ${h}`;
}

/**
 * 2-day hourly wind forecast table.
 */
function renderHourly(periods) {
  if (!hourlyListEl) return;
  hourlyListEl.innerHTML = '';
  if (!Array.isArray(periods) || periods.length === 0) {
    showSectionMessage(hourlyListEl, 'no-data');
    return;
  }
  const table = document.createElement('table');
  table.setAttribute('role', 'grid');
  table.innerHTML = `
    <thead><tr>
      <th>Date / Time</th>
      <th>Temp</th>
      <th>Wind</th>
      <th>Gusts</th>
      <th>Conditions</th>
    </tr></thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector('tbody');
  for (const p of periods) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${formatTime(p.startTime)}</td>
      <td>${p.temp ?? '—'}°F</td>
      <td>${p.windSpeed ?? '—'}</td>
      <td>${p.windGust ?? '—'}</td>
      <td>${p.shortForecast ?? '—'}</td>
    `;
    tbody.appendChild(tr);
  }
  hourlyListEl.appendChild(table);
}

/** Chart.js instance for tide chart (destroy before redraw). */
let tideChartInstance = null;

/**
 * Tide line chart (Chart.js): height (ft) vs time. Red line; data from report JSON.
 * Replaces the tide table. See https://www.chartjs.org/docs/latest/samples/line/line.html
 */
function renderTideChart(tides) {
  const canvas = document.getElementById('tide-chart');
  if (!canvas || !tideChartMessageEl) return;

  if (!Array.isArray(tides) || tides.length === 0) {
    canvas.style.display = 'none';
    tideChartMessageEl.innerHTML = '<p class="section-message section-message--no-data">No tide data available.</p>';
    tideChartMessageEl.style.display = '';
    if (tideChartInstance) {
      tideChartInstance.destroy();
      tideChartInstance = null;
    }
    return;
  }

  const labels = tides.map((t) => {
    try {
      const d = new Date(t.t.replace(' ', 'T'));
      return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    } catch {
      return t.t;
    }
  });
  const values = tides.map((t) => parseFloat(t.v) || 0);

  if (tideChartInstance) tideChartInstance.destroy();
  tideChartInstance = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Tide height (ft)',
          data: values,
          borderColor: 'rgb(179, 0, 0)',
          backgroundColor: 'rgba(179, 0, 0, 0.1)',
          fill: true,
          tension: 0.2,
          pointRadius: 4,
          pointBackgroundColor: values.map((_, i) => (tides[i].type === 'H' ? 'rgb(179, 0, 0)' : 'rgb(100, 100, 200)')),
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 2,
      plugins: {
        legend: { position: 'top' },
        title: { display: true, text: 'Tide height (ft) vs time' },
      },
      scales: {
        y: { title: { display: true, text: 'Height (ft)' } },
        x: { title: { display: true, text: 'Time' } },
      },
    },
  });

  canvas.style.display = '';
  tideChartMessageEl.innerHTML = '';
  tideChartMessageEl.style.display = 'none';
}

function setErrorState(errorMessage) {
  if (recommendationEl) recommendationEl.innerHTML = `<p class="section-message section-message--error">${escapeHtml(errorMessage)}</p>`;
  if (hourCardsEl) showSectionMessage(hourCardsEl, 'error', 'No data (report failed).');
  if (alertsListEl) showSectionMessage(alertsListEl, 'no-data');
  if (marineForecastEl) showSectionMessage(marineForecastEl, 'no-data');
  if (hourlyListEl) showSectionMessage(hourlyListEl, 'no-data');
  if (tideChartMessageEl) {
    tideChartMessageEl.innerHTML = `<p class="section-message section-message--error">${escapeHtml(errorMessage)}</p>`;
    tideChartMessageEl.style.display = '';
  }
  const tideCanvas = document.getElementById('tide-chart');
  if (tideCanvas) tideCanvas.style.display = 'none';
  if (forecast3dayListEl) showSectionMessage(forecast3dayListEl, 'no-data');
}

async function fetchReport() {
  setLoading();
  try {
    const res = await fetch(REPORT_URL);
    if (!res.ok) {
      setErrorState(`Error: ${res.status} ${res.statusText}`);
      return;
    }
    const data = await res.json();

    renderLocation(data.location || null);
    renderRecommendation(data.recommendation);
    render24HourCards(data.hourly ?? [], data.tides ?? []);
    renderAlerts(data.alerts ?? []);
    renderMarineForecast(data.marine_forecast ?? null);
    renderHourly(data.hourly ?? []);
    renderTideChart(data.tides ?? []);
    renderForecast3day(data.forecast_3day ?? []);

    if (lastFetchEl) lastFetchEl.textContent = new Date().toLocaleString();
  } catch (err) {
    const msg = err.message || 'Failed to load report.';
    setErrorState(msg);
  }
}

fetchReport();
setInterval(fetchReport, REFRESH_INTERVAL_MS);
