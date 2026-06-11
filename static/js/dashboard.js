/* ----------------------------------------------------------------------- */
/*  Dashboard – baut alle Charts aus dem eingebetteten Profil               */
/* ----------------------------------------------------------------------- */
const DATA = JSON.parse(document.getElementById('profile-data').textContent);
const P = DATA.patterns || {};

// ---- Chart.js Defaults (Dark) ----
Chart.defaults.color = '#9aa0aa';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
const GREEN = '#1db954', GREEN2 = '#1ed760', CYAN = '#22d3ee',
      VIOLET = '#8b5cf6', ROSE = '#f43f5e', AMBER = '#fbbf24';

const $ = (id) => document.getElementById(id);
const palette = [GREEN, CYAN, VIOLET, AMBER, ROSE, '#34d399', '#60a5fa',
                 '#f472b6', '#a3e635', '#fb923c'];

function gradient(ctx, area, c1, c2) {
  const g = ctx.createLinearGradient(0, area.bottom, 0, area.top);
  g.addColorStop(0, c1); g.addColorStop(1, c2);
  return g;
}

/* --------------------------- STAT STRIP --------------------------------- */
(function statStrip() {
  const lib = P.library || {};
  const mm = P.music_model || {};
  const domLabel = mm.dominant && mm.labels ? mm.labels[mm.dominant] : '–';
  const expl = P.explicit_ratio != null ? Math.round(P.explicit_ratio * 100) + '%' : '–';
  const stats = [
    [lib.gespeicherte_titel ?? '–', 'gespeicherte Titel'],
    [lib.unterschiedliche_artists ?? '–', 'verschiedene Artists'],
    [P.genre_count ?? '–', 'Genres'],
    [(P.genre_entropy != null ? Math.round(P.genre_entropy * 100) + '%' : '–'), 'Genre-Breite'],
    [expl, 'Explicit-Anteil'],
    [domLabel, 'dominanter Stil'],
  ];
  $('statStrip').innerHTML = stats.map(([n, l]) =>
    `<div class="stat"><div class="num">${n}</div><div class="lbl">${l}</div></div>`).join('');
})();

/* --------------------------- BIG FIVE ----------------------------------- */
(function bigFive() {
  const bf = P.big_five;
  if (!bf) { $('bigfive').innerHTML = '<p class="hint">Keine Daten.</p>'; return; }
  $('bfConf').textContent = 'Konfidenz gesamt: ' + bf.overall_confidence;
  const order = ['openness', 'agreeableness', 'conscientiousness'];
  const cls = (c) => /spek|sehr niedrig/i.test(c) ? 'spek' : (/niedrig|low/i.test(c) ? 'niedrig' : 'moderat');
  $('bigfive').innerHTML = order.filter(k => bf.traits[k]).map(k => {
    const t = bf.traits[k];
    const drv = (t.drivers && t.drivers.length) ? t.drivers.join(' · ') : 'keine starken Signale';
    return `<div class="trait">
      <div class="row">
        <span class="tname">${t.name}<span class="badge ${cls(t.confidence)}">${t.confidence}</span></span>
        <span class="tval">${t.score}</span>
      </div>
      <div class="bar"><span style="width:0%" data-w="${t.score}%"></span></div>
      <div class="drv">${drv}</div>
    </div>`;
  }).join('');
  // animate
  requestAnimationFrame(() => setTimeout(() =>
    document.querySelectorAll('.bar > span').forEach(s => s.style.width = s.dataset.w), 80));
  $('disclaimer').textContent = '⚠️ ' + bf.disclaimer;
})();

/* --------------------------- AVD PROFILE -------------------------------- */
(function avd() {
  const a = P.avd_profile;
  if (!a || a.arousal == null) {
    $('avdBars').innerHTML = '<p class="hint">Zu wenig Genre-Daten.</p>';
    return;
  }
  const rows = [
    ['Arousal', a.arousal, 'intensiv ↔ ruhig', ROSE],
    ['Valence', a.valence, 'fröhlich ↔ melancholisch', AMBER],
    ['Depth', a.depth, 'komplex ↔ eingängig', CYAN],
  ];
  $('avdBars').innerHTML = rows.map(([n, v, sub, col]) => `
    <div class="trait" style="margin-bottom:11px">
      <div class="row"><span class="tname">${n} <span class="drv" style="margin:0">${sub}</span></span>
        <span class="tval" style="color:${col}">${Math.round(v * 100)}</span></div>
      <div class="bar"><span style="width:0%; background:${col}" data-w="${Math.round(v * 100)}%"></span></div>
    </div>`).join('');
  requestAnimationFrame(() => setTimeout(() =>
    document.querySelectorAll('#avdBars .bar > span').forEach(s => s.style.width = s.dataset.w), 80));
  new Chart($('avdRadar'), {
    type: 'radar',
    data: { labels: ['Arousal', 'Valence', 'Depth'], datasets: [{
      data: [a.arousal * 100, a.valence * 100, a.depth * 100],
      backgroundColor: 'rgba(29,185,84,0.18)', borderColor: GREEN,
      pointBackgroundColor: GREEN2, borderWidth: 2, pointRadius: 4,
    }]},
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { r: { suggestedMin: 0, suggestedMax: 100,
        angleLines: { color: 'rgba(255,255,255,0.08)' },
        grid: { color: 'rgba(255,255,255,0.08)' },
        pointLabels: { color: '#d1d5db', font: { size: 12, weight: '600' } },
        ticks: { display: false } } },
    },
  });
})();

/* --------------------------- LIFE PHASE --------------------------------- */
(function lifePhase() {
  const lp = P.life_phase || {};
  const rem = lp.reminiscence;
  let html = '';
  if (rem) {
    html += `<div class="pill-list" style="margin-bottom:12px">
      <span class="pill">Prägende Jahre: <b>${rem.formative_peak_year}</b></span>`;
    if (rem.estimated_age_center != null) {
      html += `<span class="pill">geschätztes Alter: <b>~${rem.estimated_age_center}</b>
        (${rem.estimated_age_range[0]}–${rem.estimated_age_range[1]})</span>
        <span class="pill">Geburtsjahr ~<b>${rem.estimated_birth_year}</b></span>`;
    }
    html += `</div>
      <div class="bar" style="margin-bottom:6px"><span style="width:${Math.round(rem.bump_share*100)}%"></span></div>
      <div class="hint">${Math.round(rem.bump_share*100)}% der Bibliothek im Fenster
        ${rem.formative_window[0]}–${rem.formative_window[1]}</div>`;
  }
  html += `<div class="disclaimer" style="margin-top:14px; font-size:12px">⚠️ ${
    rem ? rem.interpretation : 'Zu wenig Daten mit Jahresangabe für eine Altersschätzung.'}</div>`;
  $('lifePhase').innerHTML = html;
})();

/* --------------------------- TRENDS ------------------------------------- */
(function trends() {
  const tr = P.trends || {};
  const cohorts = tr.cohorts || [];
  if (!cohorts.length) {
    $('trendLabels').innerHTML = '<span class="hint">Zu wenig Zeitdaten.</span>';
    return;
  }
  const s = tr.summary || {};
  const labelMap = {
    mainstream_trend: 'Mainstream', nostalgia_trend: 'Nostalgie↔Neugier',
    engagement_trend: 'Tempo', discovery_trend: 'Entdeckung',
  };
  $('trendLabels').innerHTML = Object.keys(labelMap)
    .filter(k => s[k] && s[k].label)
    .map(k => `<span class="pill">${labelMap[k]}: <b>${s[k].label}</b></span>`).join('');
  const labels = cohorts.map(c => c.year);
  const datasets = [
    { label: 'neue Titel / Jahr', data: cohorts.map(c => c.added),
      borderColor: GREEN, backgroundColor: 'transparent', borderWidth: 2.5,
      tension: 0.35, pointRadius: 3, yAxisID: 'y' },
    { label: 'Ø Musik-Alter beim Speichern (J.)', data: cohorts.map(c => c.median_music_age),
      borderColor: AMBER, backgroundColor: 'transparent', borderWidth: 2.5,
      tension: 0.35, pointRadius: 3, yAxisID: 'y1', borderDash: [5, 4] },
  ];
  // Popularität nur falls vorhanden (Spotify liefert sie für Dev-Apps nicht mehr)
  if (cohorts.some(c => c.median_popularity != null)) {
    datasets.push({ label: 'Ø Popularität', data: cohorts.map(c => c.median_popularity),
      borderColor: CYAN, backgroundColor: 'transparent', borderWidth: 2,
      tension: 0.35, pointRadius: 2, yAxisID: 'y' });
  }
  new Chart($('trendLine'), {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { boxWidth: 12, padding: 14 } } },
      scales: {
        x: { grid: { display: false } },
        y: { position: 'left', grid: { color: 'rgba(255,255,255,0.05)' },
             title: { display: true, text: 'Titel / Jahr' }, beginAtZero: true },
        y1: { position: 'right', grid: { drawOnChartArea: false },
              title: { display: true, text: 'Musik-Alter (J.)' }, beginAtZero: true },
      },
    },
  });
})();

/* --------------------------- GENRE BAR ---------------------------------- */
(function genreBar() {
  const gr = (P.genre_ranking || []).slice(0, 12);
  if (!gr.length) return;
  new Chart($('genreBar'), {
    type: 'bar',
    data: { labels: gr.map(x => x[0]), datasets: [{
      data: gr.map(x => x[1]), borderRadius: 6,
      backgroundColor: (c) => c.chart.chartArea
        ? gradient(c.chart.ctx, c.chart.chartArea, GREEN, CYAN) : GREEN,
    }]},
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { grid: { display: false }, ticks: { font: { size: 12.5 } } } },
    },
  });
})();

/* --------------------------- QUIRKS / DIVERSITY ------------------------- */
(function quirks() {
  const lib = P.library || {};
  const explicit = P.explicit_ratio;
  if (explicit != null) {
    const pct = Math.round(explicit * 100);
    new Chart($('explicitDoughnut'), {
      type: 'doughnut',
      data: { labels: ['Explicit', 'Clean'], datasets: [{
        data: [pct, 100 - pct], backgroundColor: [ROSE, 'rgba(255,255,255,0.10)'],
        borderWidth: 0,
      }]},
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '68%',
        plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, padding: 12 } },
          tooltip: { callbacks: { label: (c) => c.label + ': ' + c.raw + '%' } } },
      },
    });
  } else {
    $('explicitDoughnut').closest('.chart-box').style.display = 'none';
  }
  const pills = [];
  if (P.genre_entropy != null)
    pills.push(['Genre-Breite', Math.round(P.genre_entropy * 100) + '%']);
  if (P.avg_track_duration_min != null)
    pills.push(['Ø Track-Länge', P.avg_track_duration_min + ' min']);
  if (lib.artist_konzentration_gini != null)
    pills.push(['Konzentration (Gini)', lib.artist_konzentration_gini]);
  if (lib.top15_anteil_pct != null)
    pills.push(['Top-15-Anteil', lib.top15_anteil_pct + '%']);
  $('quirkPills').innerHTML = pills.map(([k, v]) =>
    `<span class="pill">${k}: <b>${v}</b></span>`).join('');
})();

/* --------------------------- DECADE BAR --------------------------------- */
function simpleBar(canvasId, pairs, c1, c2, fmtLabel) {
  if (!pairs || !pairs.length) return;
  new Chart($(canvasId), {
    type: 'bar',
    data: { labels: pairs.map(x => fmtLabel ? fmtLabel(x[0]) : x[0]), datasets: [{
      data: pairs.map(x => x[1]), borderRadius: 5,
      backgroundColor: (c) => c.chart.chartArea
        ? gradient(c.chart.ctx, c.chart.chartArea, c1, c2) : c1,
    }]},
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { grid: { display: false } },
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, beginAtZero: true } },
    },
  });
}
simpleBar('decadeBar', P.release_decades, CYAN, GREEN, d => d + 's');
(function eraBar() {
  const st = P.library_release_year_stats;
  if (st) $('eraHint').textContent =
    `${st['frühestes']}–${st['spätestes']}, Median ${st.median} (${st.anzahl_mit_jahr} Titel)`;
  simpleBar('eraBar', P.library_release_eras_5y, AMBER, ROSE, e => `'${String(e).slice(2)}`);
})();

/* --------------------------- TIMELINE LINE ------------------------------ */
(function timeline() {
  const months = P.library_added_by_month_recent;
  const years = P.library_added_by_year;
  let labels, data, title;
  if (months && months.length >= 4) { labels = months.map(x => x[0]); data = months.map(x => x[1]); }
  else if (years) { labels = years.map(x => String(x[0])); data = years.map(x => x[1]); }
  else return;
  new Chart($('timelineLine'), {
    type: 'line',
    data: { labels, datasets: [{
      data, label: 'gespeicherte Titel', tension: 0.35, borderColor: GREEN,
      borderWidth: 2.5, pointRadius: 2, pointHoverRadius: 5, fill: true,
      backgroundColor: (c) => {
        if (!c.chart.chartArea) return 'rgba(29,185,84,0.15)';
        const g = c.chart.ctx.createLinearGradient(0, c.chart.chartArea.top, 0, c.chart.chartArea.bottom);
        g.addColorStop(0, 'rgba(29,185,84,0.35)'); g.addColorStop(1, 'rgba(29,185,84,0.0)');
        return g;
      },
    }]},
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } },
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, beginAtZero: true } },
    },
  });
})();

/* --------------------------- DAYTIME DOUGHNUT --------------------------- */
(function daytime() {
  const d = P.listening_by_daytime;
  if (!d) return;
  const map = { nacht_0_6: 'Nacht 0–6', morgen_6_12: 'Morgen 6–12',
                nachmittag_12_18: 'Mittag 12–18', abend_18_24: 'Abend 18–24' };
  const keys = Object.keys(map);
  new Chart($('daytimeDoughnut'), {
    type: 'doughnut',
    data: { labels: keys.map(k => map[k]), datasets: [{
      data: keys.map(k => d[k] || 0),
      backgroundColor: [VIOLET, AMBER, GREEN, CYAN], borderWidth: 0,
    }]},
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '62%',
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, padding: 12 } } },
    },
  });
})();

/* --------------------------- WEEKDAY RADAR ------------------------------ */
(function weekday() {
  const w = P.listening_by_weekday;
  if (!w) { $('weekdayRadar').closest('.card').style.display = 'none'; return; }
  new Chart($('weekdayRadar'), {
    type: 'radar',
    data: { labels: ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'], datasets: [{
      data: w, backgroundColor: 'rgba(34,211,238,0.18)', borderColor: CYAN,
      pointBackgroundColor: CYAN, borderWidth: 2,
    }]},
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { r: { angleLines: { color: 'rgba(255,255,255,0.08)' },
                     grid: { color: 'rgba(255,255,255,0.08)' },
                     pointLabels: { font: { size: 12, weight: '600' } },
                     ticks: { display: false }, beginAtZero: true } },
    },
  });
})();

/* --------------------------- STABILITY BOX ------------------------------ */
(function stability() {
  const ts = P.taste_stability, lib = P.library || {};
  let html = '';
  if (ts) {
    html += `<div class="pill-list" style="margin-bottom:14px">
      <span class="pill"><b>${ts.kurz_vs_alltime_pct}%</b> kurz↔all-time</span>
      <span class="pill"><b>${ts.mittel_vs_alltime_pct}%</b> 6 Mon↔all-time</span>
      <span class="pill"><b>${ts.ueberschneidung_artists}</b> stabile Top-Artists</span>
    </div>
    <div class="hint">${ts.interpretation_hinweis}</div>`;
    if (ts.gemeinsam && ts.gemeinsam.length) {
      html += `<div class="pill-list" style="margin-top:12px">` +
        ts.gemeinsam.slice(0, 10).map(n => `<span class="pill">${n}</span>`).join('') + `</div>`;
    }
  }
  if (lib.artist_konzentration_gini != null) {
    html += `<div class="pill-list" style="margin-top:14px">
      <span class="pill">Konzentration (Gini): <b>${lib.artist_konzentration_gini}</b></span>
      <span class="pill">Top-15 = <b>${lib.top15_anteil_pct}%</b> der Titel</span>
      <span class="pill">Genre-Breite: <b>${Math.round((P.genre_entropy||0)*100)}%</b></span>
    </div>`;
  }
  $('stabilityBox').innerHTML = html || '<p class="hint">Keine Daten.</p>';
})();

/* --------------------------- TOP ARTISTS -------------------------------- */
(function artists() {
  const ta = DATA.top_artists || {};
  const ranges = [['all_time', 'All-Time'], ['letzte_6_monate', '6 Monate'], ['letzte_4_wochen', '4 Wochen']];
  const tabs = $('artistTabs'), list = $('artistList');
  function render(key) {
    const arr = ta[key] || [];
    list.innerHTML = arr.slice(0, 25).map((a, i) =>
      `<span class="pill"><b>${i + 1}.</b> ${a.name}</span>`).join('') || '<span class="hint">Keine Daten.</span>';
  }
  tabs.innerHTML = ranges.map(([k, l], i) =>
    `<span class="tab ${i === 0 ? 'active' : ''}" data-k="${k}">${l}</span>`).join('');
  tabs.querySelectorAll('.tab').forEach(t => t.onclick = () => {
    tabs.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active'); render(t.dataset.k);
  });
  render('all_time');
})();

/* --------------------------- TOP TRACKS --------------------------------- */
(function tracks() {
  const tt = (DATA.top_tracks || {}).all_time || [];
  $('trackList').innerHTML = tt.slice(0, 15).map((t, i) => {
    const img = t.image ? `<img src="${t.image}" alt="">` : `<div style="width:44px;height:44px;border-radius:8px;background:#222"></div>`;
    return `<div class="track">
      <div class="idx">${i + 1}</div>${img}
      <div class="meta">
        <div class="t">${t.name || ''}</div>
        <div class="a">${(t.artists || []).join(', ')} ${t.release_year ? '· ' + t.release_year : ''}</div>
      </div>
      <div class="pop">${t.popularity != null ? 'pop ' + t.popularity : ''}</div>
    </div>`;
  }).join('') || '<span class="hint">Keine Daten.</span>';
})();

/* --------------------------- REPLAY ------------------------------------- */
(function replay() {
  const r = P.replay;
  const box = $('replayBox');
  if (!r || !r.window_plays) {
    box.innerHTML = '<p class="hint">Zu wenig Wiedergabe-Daten.</p>';
    return;
  }
  const pct = Math.round(r.repeat_rate * 100);
  let html = '';
  if (r.obsession) {
    html += `<div style="display:flex;align-items:center;gap:14px;padding:14px;border-radius:14px;
      background:linear-gradient(90deg,rgba(244,63,94,.16),rgba(255,255,255,0.02));margin-bottom:16px">
      <div style="font-size:30px">🔥</div>
      <div><div style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em">Aktuelle Obsession</div>
      <div style="font-size:18px;font-weight:800">${r.obsession.track}</div>
      <div class="hint" style="margin:0">${r.obsession.artists} · ${r.obsession.plays}× in den letzten ${r.window_plays} Plays</div></div></div>`;
  }
  html += `<div class="trait" style="margin-bottom:14px">
    <div class="row"><span class="tname">Wiederhol-Rate <span class="drv" style="margin:0">${r.intensity}</span></span>
      <span class="tval" style="color:${ROSE}">${pct}%</span></div>
    <div class="bar"><span style="width:0%;background:linear-gradient(90deg,${ROSE},${AMBER})" data-w="${pct}%"></span></div></div>`;
  html += `<div class="pill-list" style="margin-bottom:16px">
    <span class="pill">${r.unique_tracks}/${r.window_plays} verschiedene Tracks</span>
    <span class="pill">${r.unique_artists} Artists</span>`;
  if (r.longest_streak) html += `<span class="pill">längste Schleife: <b>${r.longest_streak.plays}×</b></span>`;
  html += `<span class="pill">${r.back_to_back_loops} direkte Wiederholungen</span>`;
  if (r.plays_per_hour) html += `<span class="pill">${r.plays_per_hour} Plays/h</span>`;
  html += `</div>`;
  if (r.most_replayed && r.most_replayed.length) {
    html += `<div class="hint" style="margin-bottom:8px">Meist wiederholt</div><div class="track-list">`;
    html += r.most_replayed.map((m, i) => `<div class="track">
      <div class="idx">${i + 1}</div>
      <div class="meta"><div class="t">${m[0]}</div><div class="a">${m[1]}</div></div>
      <div class="pop">${m[2]}×</div></div>`).join('');
    html += `</div>`;
  }
  box.innerHTML = html;
  requestAnimationFrame(() => setTimeout(() =>
    box.querySelectorAll('.bar > span').forEach(s => s.style.width = s.dataset.w), 80));
})();

/* --------------------------- LLM PROMPT --------------------------------- */
(function llm() {
  const btn = $('llmBtn'), ov = $('llmOverlay'), txt = $('llmText');
  const hide = () => ov.classList.remove('show');
  btn.onclick = async () => {
    txt.textContent = 'Lade …';
    ov.classList.add('show');
    try { txt.textContent = await (await fetch('/api/llm-prompt')).text(); }
    catch (e) { txt.textContent = 'Fehler beim Laden: ' + e; }
  };
  $('llmClose').onclick = hide;
  ov.onclick = (e) => { if (e.target === ov) hide(); };
  $('llmCopy').onclick = async () => {
    try {
      await navigator.clipboard.writeText(txt.textContent);
      $('llmCopy').textContent = '✓ Kopiert';
      setTimeout(() => $('llmCopy').textContent = '📋 Kopieren', 1500);
    } catch (e) {
      const rng = document.createRange(); rng.selectNode(txt);
      getSelection().removeAllRanges(); getSelection().addRange(rng);
    }
  };
})();

/* --------------------------- REFRESH ------------------------------------ */
(function refresh() {
  const btn = $('refreshBtn'), overlay = $('overlay'), log = $('overlayLog');
  btn.onclick = async () => {
    btn.disabled = true;
    overlay.classList.add('show');
    const r = await (await fetch('/api/refresh', { method: 'POST' })).json();
    if (r.error) { log.textContent = 'Fehler: ' + r.error; return; }
    const poll = setInterval(async () => {
      const s = await (await fetch('/api/refresh/status')).json();
      log.textContent = (s.log || []).join('\n');
      log.scrollTop = log.scrollHeight;
      if (!s.running) {
        clearInterval(poll);
        if (s.error) { btn.disabled = false; }
        else { log.textContent += '\n\nLade Dashboard neu …'; setTimeout(() => location.reload(), 900); }
      }
    }, 800);
  };
})();
