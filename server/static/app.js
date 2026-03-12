/**
 * SailCast frontend: fetch /api/report and display sailing report.
 * Refreshes every hour (primary flow).
 */
const REPORT_URL = 'api/report';
const REFRESH_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

/* SCOW wind restriction thresholds (MPH) per club_rules.md */
const WIND_LIMIT_DAYSAILER_RESTRICTED = 17; // reef, lagoon-only, PFDs
const WIND_LIMIT_DAYSAILER_MAX = 23;        // no daysailers
const WIND_LIMIT_CRUISER_MAX = 29;          // no boats at all

function isMobileView() {
  return window.innerWidth <= 480;
}

function windRestrictionColor(mph) {
  if (mph > WIND_LIMIT_CRUISER_MAX)
    return { bg: 'rgba(120, 0, 0, 0.9)', border: 'rgb(120, 0, 0)' };
  if (mph > WIND_LIMIT_DAYSAILER_MAX)
    return { bg: 'rgba(211, 47, 47, 0.8)', border: 'rgb(211, 47, 47)' };
  if (mph > WIND_LIMIT_DAYSAILER_RESTRICTED)
    return { bg: 'rgba(245, 124, 0, 0.8)', border: 'rgb(245, 124, 0)' };
  return { bg: 'rgba(33, 150, 243, 0.7)', border: 'rgb(33, 150, 243)' };
}

const windThresholdLinesPlugin = {
  id: 'windThresholdLines',
  afterDraw(chart) {
    const yScale = chart.scales.y;
    if (!yScale) return;
    const ctx = chart.ctx;
    const mobile = isMobileView();
    const lines = [
      { value: WIND_LIMIT_DAYSAILER_RESTRICTED, color: 'rgba(245, 124, 0, 0.7)', label: '17', labelFull: '17 mph – Daysailer restrictions' },
      { value: WIND_LIMIT_DAYSAILER_MAX, color: 'rgba(211, 47, 47, 0.7)', label: '23', labelFull: '23 mph – No daysailers' },
      { value: WIND_LIMIT_CRUISER_MAX, color: 'rgba(120, 0, 0, 0.7)', label: '29', labelFull: '29 mph – No boats' },
    ];
    for (const line of lines) {
      if (line.value < yScale.min || line.value > yScale.max) continue;
      const y = yScale.getPixelForValue(line.value);
      ctx.save();
      ctx.beginPath();
      ctx.setLineDash(mobile ? [4, 3] : [6, 4]);
      ctx.strokeStyle = line.color;
      ctx.lineWidth = mobile ? 1 : 1.5;
      ctx.moveTo(chart.chartArea.left, y);
      ctx.lineTo(chart.chartArea.right, y);
      ctx.stroke();
      ctx.fillStyle = line.color;
      ctx.font = mobile ? '8px sans-serif' : '10px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(mobile ? line.label : line.labelFull, chart.chartArea.left + 4, y - 3);
      ctx.restore();
    }
  },
};

const locationEl = document.getElementById('location');
const lastFetchEl = document.getElementById('last-fetch');
const alertsListEl = document.getElementById('alerts-list');
const adviceCardEl = document.getElementById('advice-card');
const conditionsGridEl = document.getElementById('conditions-grid');
const tideSummaryEl = document.getElementById('tide-summary');
const forecast3dayListEl = document.getElementById('forecast-3day-list');
const hourlyListEl = document.getElementById('hourly-list');
const hourCardsEl = document.getElementById('hour-cards');
const marineForecastEl = document.getElementById('marine-forecast');
const tideChartContainerEl = document.getElementById('tide-chart-container');
const tideChartMessageEl = document.getElementById('tide-chart-message');

let _cachedReportData = null;

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

function _applySectionStates(specs) {
  for (const [el, state, msg] of specs) {
    if (el) showSectionMessage(el, state, msg);
  }
}

function _hideCanvas(id) {
  const c = document.getElementById(id);
  if (c) c.style.display = 'none';
}

function setLoading() {
  if (locationEl) locationEl.textContent = '—';
  if (adviceCardEl) adviceCardEl.innerHTML = '<p class="loading">Loading…</p>';
  if (tideSummaryEl) tideSummaryEl.innerHTML = '';
  [
    document.getElementById('metric-wind-val'),
    document.getElementById('metric-gust-val'),
    document.getElementById('metric-temp-val'),
    document.getElementById('metric-direction-val'),
    document.getElementById('metric-prev-tide-val'),
    document.getElementById('metric-tide-val'),
  ].forEach((el) => { if (el) el.textContent = '—'; });
  _applySectionStates([
    [hourCardsEl, 'loading'], [alertsListEl, 'loading'], [marineForecastEl, 'loading'],
    [hourlyListEl, 'loading'], [forecast3dayListEl, 'loading'],
  ]);
  _hideCanvas('wind-chart');
  _hideCanvas('tide-chart');
  if (tideChartMessageEl) {
    tideChartMessageEl.innerHTML = '<p class="section-message section-message--loading">Loading…</p>';
    tideChartMessageEl.style.display = '';
  }
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

/** Long format for card title: "Thursday March 5, 7:00 AM" */
function formatLongDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return iso;
  }
}

/** Map NWS shortForecast + time to weather icon filename (from static-icons / Makin-Things/weather-icons). */
function getWeatherIconName(shortForecast, startTime) {
  const s = (shortForecast || '').toLowerCase();
  const d = startTime ? new Date(startTime) : new Date();
  const hour = d.getHours();
  const day = hour >= 6 && hour < 19 ? 'day' : 'night';
  if (/clear|sunny/.test(s) && !/partly|mostly/.test(s)) return `clear-${day}`;
  if (/mostly clear|mostly sunny/.test(s)) return `cloudy-1-${day}`;
  if (/partly cloudy|partly sunny/.test(s)) return `cloudy-1-${day}`;
  if (/mostly cloudy/.test(s)) return `cloudy-2-${day}`;
  if (/overcast|cloudy/.test(s)) return `cloudy-3-${day}`;
  if (/scattered showers|showers|rain/.test(s)) return `rainy-2-${day}`;
  if (/isolated.*thunder|thunderstorm/.test(s)) return `isolated-thunderstorms-${day}`;
  if (/scattered.*thunder/.test(s)) return `scattered-thunderstorms-${day}`;
  if (/fog|patchy fog/.test(s)) return `fog-${day}`;
  if (/snow/.test(s)) return `snowy-2-${day}`;
  if (/wind/.test(s)) return 'wind';
  return `cloudy-1-${day}`;
}

function renderLocation(loc) {
  if (!locationEl || !loc) return;
  const { label, name, lat, lon } = loc;
  const parts = [label, name, `(${lat}, ${lon})`].filter(Boolean);
  locationEl.textContent = parts.join(' · ');
}

function escapeHtml(str) {
  if (str == null) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function parseMph(val) {
  if (typeof val === 'number') return val;
  if (typeof val === 'string') return parseFloat(val.replace(/[^\d.-]/g, '')) || 0;
  return 0;
}

/**
 * Check if the marine forecast contains a Small Craft Advisory.
 * Returns the advisory object with its NWS link, or null.
 */
function findSmallCraftAdvisory(marine) {
  if (!marine) return null;
  const advisories = marine.advisories || [];
  for (const a of advisories) {
    if (/small craft advisory/i.test(a.label)) return a;
  }
  const text = marine.forecast_text || '';
  if (/small craft advisory/i.test(text)) {
    return { label: 'Small Craft Advisory', url: marine.url || null };
  }
  return null;
}

/**
 * Compute safety level from raw hourly + alerts + marine data (client-side fallback).
 * Uses SCOW club rule thresholds: 17/23/29 MPH.
 * A Small Craft Advisory in the marine forecast = UNSAFE (no boats out).
 */
function computeSafetyLevel(hourly, alerts, marine) {
  if (findSmallCraftAdvisory(marine)) return 'UNSAFE';
  if (Array.isArray(alerts)) {
    for (const a of alerts) {
      const sev = (a.severity || '').toLowerCase();
      if (sev === 'severe' || sev === 'extreme') return 'UNSAFE';
    }
  }
  if (Array.isArray(hourly) && hourly.length > 0) {
    const p = hourly[0];
    const wind = parseMph(p.windSpeed);
    const gust = parseMph(p.windGust);
    if (wind > WIND_LIMIT_DAYSAILER_MAX || gust > WIND_LIMIT_CRUISER_MAX) return 'UNSAFE';
    if (wind > WIND_LIMIT_DAYSAILER_RESTRICTED || gust > WIND_LIMIT_DAYSAILER_MAX) return 'CAUTION';
  }
  return 'SAFE';
}

/**
 * Scan hourly periods for the longest consecutive SAFE stretch during daylight (6am-7pm).
 * Returns a string like "11:00 AM – 3:00 PM" or null.
 */
function findBestWindow(hourly) {
  if (!Array.isArray(hourly) || hourly.length === 0) return null;

  let bestStart = null;
  let bestLen = 0;
  let curStart = null;
  let curLen = 0;

  for (const p of hourly) {
    const d = new Date(p.startTime);
    const hour = d.getHours();
    const isDaylight = hour >= 6 && hour < 19;
    const wind = parseMph(p.windSpeed);
    const gust = parseMph(p.windGust);
    const safe = isDaylight && wind <= WIND_LIMIT_DAYSAILER_RESTRICTED && gust <= WIND_LIMIT_DAYSAILER_MAX;

    if (safe) {
      if (curStart === null) curStart = p.startTime;
      curLen++;
    } else {
      if (curLen > bestLen) {
        bestStart = curStart;
        bestLen = curLen;
      }
      curStart = null;
      curLen = 0;
    }
  }
  if (curLen > bestLen) {
    bestStart = curStart;
    bestLen = curLen;
  }

  if (!bestStart || bestLen === 0) return null;

  const fmt = (d) => d.toLocaleString(undefined, { hour: 'numeric', minute: '2-digit', hour12: true });
  const startD = new Date(bestStart);
  const endD = new Date(startD.getTime() + bestLen * 3600000);
  return `${fmt(startD)} – ${fmt(endD)}`;
}

const SAFETY_COLORS = {
  SAFE: { border: '#2e7d32', bg: '#e8f5e9', badge: '#2e7d32', text: 'Safe to Sail' },
  CAUTION: { border: '#f9a825', bg: '#fff8e1', badge: '#f57f17', text: 'Caution' },
  UNSAFE: { border: '#c62828', bg: '#ffebee', badge: '#c62828', text: 'Unsafe' },
};

function renderAdviceCard(data) {
  if (!adviceCardEl) return;
  adviceCardEl.innerHTML = '';

  const advice = data.advice || null;
  const marine = data.marine_forecast || null;
  const sca = findSmallCraftAdvisory(marine);

  let level = (advice && advice.safetyLevel) || computeSafetyLevel(data.hourly || [], data.alerts || [], marine);
  if (sca && level !== 'UNSAFE') level = 'UNSAFE';
  const colors = SAFETY_COLORS[level] || SAFETY_COLORS.SAFE;

  adviceCardEl.style.borderLeftColor = colors.border;
  adviceCardEl.style.backgroundColor = colors.bg;

  const badge = document.createElement('span');
  badge.className = 'advice-badge';
  badge.style.backgroundColor = colors.badge;
  badge.textContent = colors.text;
  adviceCardEl.appendChild(badge);

  if (sca) {
    const scaDiv = document.createElement('div');
    scaDiv.className = 'advice-sca-warning';
    const icon = '\u26A0\uFE0F ';
    const msg = document.createElement('span');
    msg.textContent = icon + 'Small Craft Advisory is in effect — club boats may not leave the dock. ';
    scaDiv.appendChild(msg);
    if (sca.url) {
      const link = document.createElement('a');
      link.href = sca.url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = 'View NWS Advisory';
      scaDiv.appendChild(link);
    }
    adviceCardEl.appendChild(scaDiv);
  }

  const summary = (advice && advice.summary) || data.recommendation || '';
  if (summary) {
    const p = document.createElement('p');
    p.className = 'advice-summary';
    p.textContent = summary;
    adviceCardEl.appendChild(p);
  }

  const advisory = advice && advice.advisory;
  if (advisory) {
    const p = document.createElement('p');
    p.className = 'advice-advisory';
    p.textContent = advisory;
    adviceCardEl.appendChild(p);
  }

  const concerns = (advice && advice.keyConcerns) || [];
  if (concerns.length > 0) {
    const ul = document.createElement('ul');
    ul.className = 'advice-concerns';
    for (const c of concerns) {
      const li = document.createElement('li');
      li.textContent = c;
      ul.appendChild(li);
    }
    adviceCardEl.appendChild(ul);
  }

  const bestWindow = findBestWindow(data.hourly || []);
  if (bestWindow && !sca) {
    const p = document.createElement('p');
    p.className = 'advice-window meta';
    p.textContent = `Best sailing window: ${bestWindow}`;
    adviceCardEl.appendChild(p);
  }

  if (advice && advice.generatedAt) {
    const p = document.createElement('p');
    p.className = 'advice-meta meta';
    p.textContent = `AI-generated${advice.model ? ` (${advice.model})` : ''} at ${formatTime(advice.generatedAt)}`;
    adviceCardEl.appendChild(p);
  }
}

function renderConditionsGrid(hourly, tides) {
  if (!conditionsGridEl) return;
  const windVal = document.getElementById('metric-wind-val');
  const gustVal = document.getElementById('metric-gust-val');
  const tempVal = document.getElementById('metric-temp-val');
  const dirVal = document.getElementById('metric-direction-val');
  const tideVal = document.getElementById('metric-tide-val');
  const prevTideVal = document.getElementById('metric-prev-tide-val');

  if (!Array.isArray(hourly) || hourly.length === 0) {
    [windVal, gustVal, tempVal, dirVal, tideVal, prevTideVal].forEach((el) => { if (el) el.textContent = '—'; });
    return;
  }

  const p = hourly[0];
  if (windVal) windVal.textContent = p.windSpeed || '—';
  if (gustVal) gustVal.textContent = p.windGust || '—';
  if (tempVal) tempVal.textContent = p.temp != null ? `${p.temp}°F` : '—';
  if (dirVal) dirVal.textContent = p.windDirection || '—';

  if (tideVal) {
    const nextTide = findNextTide(tides);
    tideVal.textContent = nextTide || '—';
  }
  if (prevTideVal) {
    const prevTide = findPreviousTide(tides);
    prevTideVal.textContent = prevTide || '—';
  }
}

function findNextTide(tides) {
  if (!Array.isArray(tides) || tides.length === 0) return null;
  const now = Date.now();
  for (const t of tides) {
    const d = new Date(t.t.replace(' ', 'T'));
    if (d.getTime() >= now) {
      const label = t.type === 'H' ? 'High' : t.type === 'L' ? 'Low' : '';
      const time = d.toLocaleString(undefined, { hour: 'numeric', minute: '2-digit', hour12: true });
      return `${label} ${t.v || ''} ft @ ${time}`.trim();
    }
  }
  return null;
}

function findPreviousTide(tides) {
  if (!Array.isArray(tides) || tides.length === 0) return null;
  const now = Date.now();
  let prev = null;
  for (const t of tides) {
    const d = new Date(t.t.replace(' ', 'T'));
    if (d.getTime() >= now) break;
    prev = t;
  }
  if (!prev) return null;
  const d = new Date(prev.t.replace(' ', 'T'));
  const label = prev.type === 'H' ? 'High' : prev.type === 'L' ? 'Low' : '';
  const time = d.toLocaleString(undefined, { hour: 'numeric', minute: '2-digit', hour12: true });
  return `${label} ${prev.v || ''} ft @ ${time}`.trim();
}

function renderTideSummary(tides) {
  if (!tideSummaryEl) return;
  tideSummaryEl.innerHTML = '';
  if (!Array.isArray(tides) || tides.length === 0) return;

  const now = Date.now();
  let nextHigh = null;
  let nextLow = null;
  for (const t of tides) {
    const d = new Date(t.t.replace(' ', 'T'));
    if (d.getTime() < now) continue;
    const fmt = d.toLocaleString(undefined, { hour: 'numeric', minute: '2-digit', hour12: true });
    if (t.type === 'H' && !nextHigh) nextHigh = `High ${t.v} ft @ ${fmt}`;
    if (t.type === 'L' && !nextLow) nextLow = `Low ${t.v} ft @ ${fmt}`;
    if (nextHigh && nextLow) break;
  }

  const parts = [nextHigh, nextLow].filter(Boolean);
  if (parts.length > 0) {
    const p = document.createElement('p');
    p.className = 'meta';
    p.textContent = parts.join('  |  ');
    tideSummaryEl.appendChild(p);
  }
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
 * Render 24 hours forecast cards: long date, icon, description, temp, wind, tide.
 * Icons from /static-icons (Makin-Things/weather-icons SVGs in server/static-icons).
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
    const iconName = getWeatherIconName(p.shortForecast, p.startTime);
    const conditions = p.shortForecast ?? '—';
    const temp = p.temp != null ? `${p.temp}°F` : '—';
    const card = document.createElement('article');
    card.className = 'hour-card';
    card.innerHTML = `
      <header class="hour-card-date">${escapeHtml(formatLongDate(p.startTime))}</header>
      <div class="hour-card-icon" aria-hidden="true">
        <img src="static-icons/${escapeHtml(iconName)}.svg" alt="" width="48" height="48" loading="lazy" onerror="this.style.display='none'">
      </div>
      <p class="hour-card-conditions">${escapeHtml(conditions)}</p>
      <p class="hour-card-temp meta">${escapeHtml(temp)}</p>
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
 * Render NWS marine zone forecast (ANZ535) as a standalone card.
 * Highlights red when advisories include Small Craft Advisory or Hazardous Weather.
 */
function renderMarineForecast(marine) {
  if (!marineForecastEl) return;
  marineForecastEl.innerHTML = '';
  if (!marine || (!marine.forecast_text && !marine.error)) {
    showSectionMessage(marineForecastEl, 'no-data');
    return;
  }
  const name = marine.name || marine.zone_id || 'ANZ535';
  const advisories = marine.advisories || [];
  const periods = marine.periods || [];
  const text = marine.error || marine.forecast_text || '';

  const hasHazard = advisories.some((a) => /small craft advisory|hazardous weather/i.test(a.label))
    || /small craft advisory|hazardous weather/i.test(text);

  const card = document.createElement('div');
  card.className = 'marine-card' + (hasHazard ? ' marine-card--hazard' : '');
  card.setAttribute('role', 'region');
  card.setAttribute('aria-label', 'NWS Marine forecast');

  const heading = document.createElement('h4');
  heading.className = 'marine-card__heading';
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
  card.appendChild(heading);

  if (advisories.length > 0) {
    const advDiv = document.createElement('div');
    advDiv.className = 'marine-advisories';
    for (const adv of advisories) {
      const a = document.createElement('a');
      a.href = adv.url;
      a.target = '_blank';
      a.rel = 'noopener';
      a.className = 'marine-advisory-link';
      a.textContent = adv.label;
      advDiv.appendChild(a);
    }
    card.appendChild(advDiv);
  }

  if (periods.length > 0) {
    const list = document.createElement('dl');
    list.className = 'marine-periods';
    for (const p of periods) {
      const dt = document.createElement('dt');
      dt.textContent = p.name;
      const dd = document.createElement('dd');
      dd.textContent = p.forecast;
      list.appendChild(dt);
      list.appendChild(dd);
    }
    card.appendChild(list);
  } else {
    const para = document.createElement('p');
    para.className = 'marine-card__text';
    para.textContent = text;
    card.appendChild(para);
  }

  marineForecastEl.appendChild(card);
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
 * Time filter: slice the cached hourly data and re-render the wind chart + hourly table.
 */
function applyTimeFilter(filterName) {
  if (!_cachedReportData) return;
  const hourly = _cachedReportData.hourly || [];
  if (hourly.length === 0) return;

  const now = new Date();
  let filtered;

  switch (filterName) {
    case '4hr':
      filtered = hourly.filter((p) => {
        const d = new Date(p.startTime);
        return d >= now && d <= new Date(now.getTime() + 4 * 3600000);
      });
      break;
    case '6hr':
      filtered = hourly.filter((p) => {
        const d = new Date(p.startTime);
        return d >= now && d <= new Date(now.getTime() + 6 * 3600000);
      });
      break;
    case 'today': {
      const endOfDay = new Date(now);
      endOfDay.setHours(23, 59, 59, 999);
      filtered = hourly.filter((p) => new Date(p.startTime) <= endOfDay);
      break;
    }
    case 'tomorrow': {
      const tmrwStart = new Date(now);
      tmrwStart.setDate(tmrwStart.getDate() + 1);
      tmrwStart.setHours(0, 0, 0, 0);
      const tmrwEnd = new Date(tmrwStart);
      tmrwEnd.setHours(23, 59, 59, 999);
      filtered = hourly.filter((p) => {
        const d = new Date(p.startTime);
        return d >= tmrwStart && d <= tmrwEnd;
      });
      break;
    }
    default: {
      const eod = new Date(now);
      eod.setHours(23, 59, 59, 999);
      filtered = hourly.filter((p) => new Date(p.startTime) <= eod);
      break;
    }
  }

  if (filtered.length === 0) filtered = hourly.slice(0, 1);
  renderWindChart(filtered);
  renderHourly(filtered);
}

function initTimeFilter() {
  const buttons = document.querySelectorAll('.time-filter-btn');
  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      buttons.forEach((b) => b.classList.remove('time-filter-btn--active'));
      btn.classList.add('time-filter-btn--active');
      applyTimeFilter(btn.dataset.filter);
    });
  });
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
      <th>Wind</th>
      <th>Gusts</th>
    </tr></thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector('tbody');
  for (const p of periods) {
    const tr = document.createElement('tr');
    const mph = parseFloat(String(p.windSpeed ?? '0').replace(/[^\d.-]/g, '')) || 0;
    if (mph > WIND_LIMIT_CRUISER_MAX) tr.className = 'wind-row--no-sail';
    else if (mph > WIND_LIMIT_DAYSAILER_MAX) tr.className = 'wind-row--danger';
    else if (mph > WIND_LIMIT_DAYSAILER_RESTRICTED) tr.className = 'wind-row--caution';
    tr.innerHTML = `
      <td>${formatTime(p.startTime)}</td>
      <td>${p.windSpeed ?? '—'}</td>
      <td>${p.windGust ?? '—'}</td>
    `;
    tbody.appendChild(tr);
  }
  hourlyListEl.appendChild(table);
}

/** Chart.js instance for wind bar chart (destroy before redraw). */
let windChartInstance = null;

/**
 * Bar chart: next 8 hours wind speed (mph). Uses first 8 periods from hourly data.
 */
function renderWindChart(periods) {
  const canvas = document.getElementById('wind-chart');
  if (!canvas) return;

  const next8 = Array.isArray(periods) ? periods.slice(0, 8) : [];
  if (next8.length === 0) {
    if (windChartInstance) {
      windChartInstance.destroy();
      windChartInstance = null;
    }
    canvas.style.display = 'none';
    return;
  }

  const labels = next8.map((p) => {
    try {
      const d = new Date(p.startTime);
      return d.toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' });
    } catch {
      return p.startTime || '—';
    }
  });
  const windValues = next8.map((p) => {
    const v = p.windSpeed;
    if (typeof v === 'number') return v;
    if (typeof v === 'string') return parseFloat(v.replace(/[^\d.-]/g, '')) || 0;
    return 0;
  });

  const barColors = windValues.map((mph) => windRestrictionColor(mph));

  const maxWind = Math.max(...windValues, 0);
  const yMax = Math.max(maxWind + 5, WIND_LIMIT_CRUISER_MAX + 4);

  const mobile = isMobileView();

  if (windChartInstance) windChartInstance.destroy();
  windChartInstance = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Wind (mph)',
          data: windValues,
          backgroundColor: barColors.map((c) => c.bg),
          borderColor: barColors.map((c) => c.border),
          borderWidth: 1,
          barPercentage: mobile ? 0.6 : 0.9,
          categoryPercentage: mobile ? 0.7 : 0.8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: mobile ? 1.4 : 2,
      plugins: {
        legend: { display: !mobile },
        title: { display: true, text: 'Next 8 hours wind speed', font: { size: mobile ? 11 : 14 } },
        tooltip: { enabled: true, intersect: false, mode: 'index' },
      },
      scales: {
        y: {
          beginAtZero: true,
          max: yMax,
          title: { display: !mobile, text: 'Wind (mph)' },
          ticks: { font: { size: mobile ? 9 : 12 } },
        },
        x: {
          title: { display: false },
          ticks: {
            font: { size: mobile ? 8 : 12 },
            maxRotation: mobile ? 45 : 0,
            callback: mobile
              ? function (val, idx) {
                  const lbl = this.getLabelForValue(val);
                  const parts = lbl.split(',');
                  return parts.length > 1 ? parts[1].trim() : lbl;
                }
              : undefined,
          },
        },
      },
    },
    plugins: [windThresholdLinesPlugin],
  });

  canvas.style.display = '';
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

  const mobile = isMobileView();

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
          borderWidth: mobile ? 1.5 : 2,
          pointRadius: mobile ? 2.5 : 4,
          pointHitRadius: mobile ? 16 : 8,
          pointBackgroundColor: values.map((_, i) => (tides[i].type === 'H' ? 'rgb(179, 0, 0)' : 'rgb(100, 100, 200)')),
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: mobile ? 1.4 : 2,
      plugins: {
        legend: { display: !mobile },
        title: { display: true, text: 'Tide height (ft) vs time', font: { size: mobile ? 11 : 14 } },
        tooltip: { enabled: true, intersect: false, mode: 'index' },
      },
      scales: {
        y: {
          title: { display: !mobile, text: 'Height (ft)' },
          ticks: { font: { size: mobile ? 9 : 12 } },
        },
        x: {
          title: { display: false },
          ticks: {
            font: { size: mobile ? 8 : 12 },
            maxRotation: mobile ? 45 : 0,
            maxTicksLimit: mobile ? 6 : undefined,
            callback: mobile
              ? function (val, idx) {
                  const lbl = this.getLabelForValue(val);
                  const parts = lbl.split(',');
                  return parts.length > 1 ? parts[1].trim() : lbl;
                }
              : undefined,
          },
        },
      },
    },
  });

  canvas.style.display = '';
  tideChartMessageEl.innerHTML = '';
  tideChartMessageEl.style.display = 'none';
}

function setErrorState(errorMessage) {
  if (adviceCardEl) {
    adviceCardEl.style.borderLeftColor = SAFETY_COLORS.UNSAFE.border;
    adviceCardEl.style.backgroundColor = SAFETY_COLORS.UNSAFE.bg;
    adviceCardEl.innerHTML = `<p class="section-message section-message--error">${escapeHtml(errorMessage)}</p>`;
  }
  if (tideSummaryEl) tideSummaryEl.innerHTML = '';
  _applySectionStates([
    [hourCardsEl, 'error', 'No data (report failed).'],
    [alertsListEl, 'no-data'], [marineForecastEl, 'no-data'],
    [hourlyListEl, 'no-data'], [forecast3dayListEl, 'no-data'],
  ]);
  if (windChartInstance) { windChartInstance.destroy(); windChartInstance = null; }
  _hideCanvas('wind-chart');
  _hideCanvas('tide-chart');
  if (tideChartMessageEl) {
    tideChartMessageEl.innerHTML = `<p class="section-message section-message--error">${escapeHtml(errorMessage)}</p>`;
    tideChartMessageEl.style.display = '';
  }
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
    _cachedReportData = data;

    renderLocation(data.location || null);
    renderAlerts(data.alerts ?? []);
    renderAdviceCard(data);
    renderConditionsGrid(data.hourly ?? [], data.tides ?? []);
    const activeFilter = document.querySelector('.time-filter-btn--active');
    applyTimeFilter(activeFilter ? activeFilter.dataset.filter : '4hr');
    renderTideSummary(data.tides ?? []);
    renderTideChart(data.tides ?? []);
    render24HourCards(data.hourly ?? [], data.tides ?? []);
    renderMarineForecast(data.marine_forecast ?? null);
    renderForecast3day(data.forecast_3day ?? []);

    if (lastFetchEl) lastFetchEl.textContent = new Date().toLocaleString();
  } catch (err) {
    const msg = err.message || 'Failed to load report.';
    setErrorState(msg);
  }
}

initTimeFilter();
fetchReport();
setInterval(fetchReport, REFRESH_INTERVAL_MS);
