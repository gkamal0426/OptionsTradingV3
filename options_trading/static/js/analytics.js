// ═══════════════════════════════════════════════
//  analytics.js  —  Analytics page
// ═══════════════════════════════════════════════

// ── Shared state ────────────────────────────────
let _pcrData         = null;   // cached after every load
let _currentStrikeRow = null;  // PCR strike modal
let _currentOicRow    = null;  // OIC strike modal
let _oicChart         = null;  // Chart.js instance — destroyed before re-render
let _dirMap           = {};    // populated from /api/config/pcr

// ── Init ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('dateFilter').value = new Date().toISOString().split('T')[0];
    await loadPcrConfig();
    loadPCR();

    setInterval(() => {
        const date  = document.getElementById('dateFilter').value;
        const today = new Date().toISOString().split('T')[0];
        if (date === today) loadPCR(true);
    }, 30000);
});

// ── Config from YAML via Flask ───────────────────
async function loadPcrConfig() {
    try {
        const res  = await fetch('/api/config/pcr');
        const json = await res.json();
        for (const key of Object.keys(json.direction || {})) {
            const k = key.toLowerCase();
            if      (k.includes('bear'))                          _dirMap[k] = 'bear';
            else if (k.includes('bull'))                          _dirMap[k] = 'bull';
            else if (k.includes('neut') || k.includes('range'))  _dirMap[k] = 'neut';
            else                                                  _dirMap[k] = 'unk';
        }
    } catch (e) {
        console.warn('PCR config load failed — using inline fallback', e);
    }
}

// ── Page tab switching ───────────────────────────
function switchAnaTab(index) {
    document.querySelectorAll('.ana-tab-btn').forEach((b, i) =>
        b.classList.toggle('active', i === index));
    document.querySelectorAll('.ana-tab-panel').forEach((p, i) =>
        p.classList.toggle('active', i === index));

    if (index === 1 && _pcrData) renderOicTab(_pcrData);
}

// ═══════════════════════════════════════════════
//  PCR — TAB 0
// ═══════════════════════════════════════════════

async function loadPCR(silent = false) {
    const date  = document.getElementById('dateFilter').value;
    const tbody = document.getElementById('pcrTableBody');

    if (!silent) {
        tbody.innerHTML = `<tr class="ana-empty-row"><td colspan="8">⏳ Loading…</td></tr>`;
    }

    try {
        const res  = await fetch(`/api/pcr/history/${date}`);
        const json = await res.json();

        if (json.status !== 'ok' || !json.data?.length) {
            if (!silent) {
                tbody.innerHTML = `<tr class="ana-empty-row">
                    <td colspan="8" style="color:#dc2626;">
                        📭 ${json.message || 'No data for ' + date}
                    </td></tr>`;
                document.getElementById('pcrLiveSummary').style.display = 'none';
                document.getElementById('oicLiveSummary').style.display = 'none';
            }
            return;
        }

        _pcrData = json.data;
        renderPcrSummary(_pcrData);
        renderPcrTable(_pcrData);
        document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();

        // Refresh OIC tab too if it's visible
        const oicPanel = document.getElementById('anaPanel1');
        if (oicPanel?.classList.contains('active')) renderOicTab(_pcrData);

    } catch (e) {
        if (!silent) {
            tbody.innerHTML = `<tr class="ana-empty-row">
                <td colspan="8" style="color:#dc2626;">❌ Error: ${e.message}</td></tr>`;
        }
    }
}

async function startPCR() {
    const index   = parseInt(document.getElementById('pcrIndexSelect').value);
    const itm     = parseInt(document.getElementById('itmstrikes').value) || 5;
    const otm     = parseInt(document.getElementById('otmstrikes').value) || 15;
    const userKey = document.getElementById('globalUserSelect')?.value || 'client1';
    try {
        const res  = await fetch('/api/pcr/start', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ index, user: userKey, itm, otm })
        });
        const json = await res.json();
        updateStatusDot(json.status === 'ok');
        alert(json.message);
    } catch (e) { alert('Error: ' + e.message); }
}

async function stopPCR() {
    try {
        const res  = await fetch('/api/pcr/stop', { method: 'POST' });
        const json = await res.json();
        updateStatusDot(false);
        alert(json.message);
    } catch (e) { alert('Error: ' + e.message); }
}

function updateStatusDot(running) {
    const el = document.getElementById('pcrStatusDot');
    if (!el) return;
    el.textContent = running ? '🟢 Running' : '⚫ Stopped';
    el.style.color = running ? '#16a34a'    : '#64748b';
}

function renderPcrSummary(data) {
    const last       = data[data.length - 1];
    const sel        = document.getElementById('pcrIndexSelect');
    const indexLabel = sel?.options[sel.selectedIndex]?.text || '—';

    document.getElementById('sumIndex').textContent    = indexLabel;
    document.getElementById('sumLtp').textContent      = last.index_ltp?.toLocaleString('en-IN') ?? '—';
    document.getElementById('sumCallOi').textContent   = formatOI(last.call_oi);
    document.getElementById('sumPutOi').textContent    = formatOI(last.put_oi);
    document.getElementById('sumPcr').textContent      = ((last.ratio ?? 0) * 100).toFixed(2) + '%';
    document.getElementById('sumReadings').textContent = data.length;
    document.getElementById('sumTime').textContent     = last.time ?? '—';

    const dirEl = document.getElementById('sumDirection');
    dirEl.textContent = last.direction ?? '—';
    dirEl.className   = 'pcr-sum-val ' + dirClass(last.direction);

    document.getElementById('pcrLiveSummary').style.display = 'flex';
}

function renderPcrTable(data) {
    const tbody = document.getElementById('pcrTableBody');
    tbody.innerHTML = [...data].reverse().map(row => {
        const pct   = ((row.ratio ?? 0) * 100).toFixed(2);
        const badge = dirClass(row.direction);
        return `<tr>
            <td style="color:#94a3b8;">${row.SNo}</td>
            <td style="color:#64748b;white-space:nowrap;">${row.time}</td>
            <td style="font-weight:700;">${row.index_ltp?.toLocaleString('en-IN') ?? '—'}</td>
            <td style="color:#2563eb;">${formatOI(row.call_oi)}</td>
            <td style="color:#dc2626;">${formatOI(row.put_oi)}</td>
            <td style="font-weight:700;color:#667eea;">${pct}%</td>
            <td><span class="pcr-dir-badge ${badge}">${row.direction ?? '—'}</span></td>
            <td>
                <button class="pcr-view-btn"
                        onclick='openStrikeModal(${JSON.stringify(row)})'>
                    🔍 Strikes
                </button>
            </td>
        </tr>`;
    }).join('');
}

// ═══════════════════════════════════════════════
//  PCR — STRIKE DETAIL MODAL (Tab 0)
// ═══════════════════════════════════════════════

function openStrikeModal(row) {
    _currentStrikeRow = row;
    document.getElementById('strikeModalTitle').textContent =
        `${row.time}  |  PCR: ${((row.ratio ?? 0) * 100).toFixed(2)}%`;

    switchStrikeTab(0);

    const strikes = [...(row.strikes || [])].sort((a, b) => {
        if (a.tag !== b.tag) return a.tag === 'CE' ? -1 : 1;
        return (a.strike ?? 0) - (b.strike ?? 0);
    });

    document.getElementById('strikeModalBody').innerHTML = strikes.length
        ? strikes.map(s => `<tr>
                <td style="font-weight:600;">${s.strike ?? '—'}</td>
                <td><span class="tag-${(s.tag || '').toLowerCase()}">${s.tag ?? '—'}</span></td>
                <td style="font-size:11px;color:#64748b;">${s.symbol ?? '—'}</td>
                <td class="num">${formatOI(s.open_int)}</td>
                <td class="num">${s.lot_size ?? '—'}</td>
            </tr>`).join('')
        : `<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:20px;">No strike data</td></tr>`;

    document.getElementById('strikeModal').style.display = 'flex';
}

function closeStrikeModal() {
    document.getElementById('strikeModal').style.display = 'none';
    _currentStrikeRow = null;
}

function switchStrikeTab(index) {
    const modal = document.getElementById('strikeModal');
    modal.querySelectorAll('.ana-modal-tab').forEach((b, i)   => b.classList.toggle('active', i === index));
    modal.querySelectorAll('.ana-modal-tab-panel').forEach((p, i) => p.classList.toggle('active', i === index));
    if (index === 1 && _currentStrikeRow) renderOiChart(_currentStrikeRow.strikes || []);
}

// ═══════════════════════════════════════════════
//  PCR — OI BAR CHART (pure SVG, no dependencies)
// ═══════════════════════════════════════════════

function renderOiChart(strikes) {
    const container = document.getElementById('strikeOiChart');
    if (!container) return;

    const map = {};
    for (const s of strikes) {
        const k = s.strike ?? 0;
        if (!map[k]) map[k] = { ce: 0, pe: 0 };
        if ((s.tag || '').toUpperCase() === 'CE') map[k].ce = s.open_int ?? 0;
        if ((s.tag || '').toUpperCase() === 'PE') map[k].pe = s.open_int ?? 0;
    }
    const keys = Object.keys(map).map(Number).sort((a, b) => a - b);
    if (!keys.length) {
        container.innerHTML = '<p style="text-align:center;color:#94a3b8;padding:40px;">No data</p>';
        return;
    }

    const BAR_W = 22, BAR_GAP = 4, GROUP_W = BAR_W * 2 + BAR_GAP, GROUP_GAP = 14;
    const PAD_LEFT = 70, PAD_RIGHT = 20, PAD_TOP = 20, PAD_BOT = 50, CHART_H = 260;
    const totalW = PAD_LEFT + keys.length * (GROUP_W + GROUP_GAP) - GROUP_GAP + PAD_RIGHT;
    const svgH   = PAD_TOP + CHART_H + PAD_BOT;
    const maxOI  = Math.max(...keys.map(k => Math.max(map[k].ce, map[k].pe)), 1);
    const scaleY = v => CHART_H - Math.round((v / maxOI) * CHART_H);
    const TICKS  = 5;

    const yTickLines = Array.from({ length: TICKS + 1 }, (_, i) => Math.round((maxOI / TICKS) * i)).map(t => {
        const y = PAD_TOP + scaleY(t);
        return `<line x1="${PAD_LEFT}" y1="${y}" x2="${totalW - PAD_RIGHT}" y2="${y}" stroke="#e2e8f0" stroke-width="1"/>
                <text x="${PAD_LEFT - 6}" y="${y + 4}" text-anchor="end" font-size="10" fill="#94a3b8">${formatOI(t)}</text>`;
    }).join('');

    const bars = keys.map((strike, i) => {
        const x0  = PAD_LEFT + i * (GROUP_W + GROUP_GAP);
        const ceH = Math.round((map[strike].ce / maxOI) * CHART_H);
        const peH = Math.round((map[strike].pe / maxOI) * CHART_H);
        const ceY = PAD_TOP + CHART_H - ceH;
        const peY = PAD_TOP + CHART_H - peH;
        const midX = x0 + GROUP_W / 2;
        return `
            <rect x="${x0}" y="${peY}" width="${BAR_W}" height="${peH}" fill="#ef4444" rx="2" data-tip="PE ${strike}: ${formatOI(map[strike].pe)}"/>
            <rect x="${x0 + BAR_W + BAR_GAP}" y="${ceY}" width="${BAR_W}" height="${ceH}" fill="#3b82f6" rx="2" data-tip="CE ${strike}: ${formatOI(map[strike].ce)}"/>
            <text x="${midX}" y="${PAD_TOP + CHART_H + 18}" text-anchor="middle" font-size="9" fill="#64748b"
                  transform="rotate(-45,${midX},${PAD_TOP + CHART_H + 18})">${strike}</text>`;
    }).join('');

    container.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="${totalW}" height="${svgH}" style="display:block;font-family:inherit;">
            ${yTickLines}
            <line x1="${PAD_LEFT}" y1="${PAD_TOP + CHART_H}" x2="${totalW - PAD_RIGHT}" y2="${PAD_TOP + CHART_H}" stroke="#cbd5e1" stroke-width="1.5"/>
            ${bars}
        </svg>`;

    container.querySelectorAll('rect[data-tip]').forEach(r => {
        const tip = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        tip.textContent = r.getAttribute('data-tip');
        r.appendChild(tip);
    });
}

// ═══════════════════════════════════════════════
//  OI CHANGE — TAB 1
// ═══════════════════════════════════════════════

function renderOicTab(data) {
    if (!data?.length) return;
    renderOicSummary(data);
    renderOicTable(data);
    document.getElementById('oicLastUpdate').textContent = new Date().toLocaleTimeString();
}

// ── OIC Summary Strip ────────────────────────────
function renderOicSummary(data) {
    const last = data[data.length - 1];
    const cc   = last.call_oi_change ?? null;
    const pc   = last.put_oi_change  ?? null;
    const net  = (cc ?? 0) + (pc ?? 0);

    const setChg = (id, val) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = formatChg(val);
        el.style.color = chgColor(val);
    };

    setChg('oicSumCallChg', cc);
    setChg('oicSumPutChg',  pc);
    setChg('oicSumNetChg',  net);

    // Net highlight colour
    const netEl = document.getElementById('oicSumNetChg');
    if (netEl) netEl.style.fontWeight = '800';

    // Top builders from latest reading's strikes
    const { topCe, topPe } = getTopBuilders(last.strikes || []);

    const ceStrikeEl = document.getElementById('oicSumCeStrike');
    const ceChgEl    = document.getElementById('oicSumCeChg');
    const peStrikeEl = document.getElementById('oicSumPeStrike');
    const peChgEl    = document.getElementById('oicSumPeChg');

    if (ceStrikeEl) ceStrikeEl.textContent = topCe?.strike ?? '—';
    if (ceChgEl && topCe) {
        ceChgEl.textContent = formatChg(topCe.chg);
        ceChgEl.style.color = chgColor(topCe.chg);
    }
    if (peStrikeEl) peStrikeEl.textContent = topPe?.strike ?? '—';
    if (peChgEl && topPe) {
        peChgEl.textContent = formatChg(topPe.chg);
        peChgEl.style.color = chgColor(topPe.chg);
    }

    const dirEl = document.getElementById('oicSumDirection');
    if (dirEl) {
        dirEl.textContent = last.direction ?? '—';
        dirEl.className   = 'pcr-sum-val ' + dirClass(last.direction);
    }

    const rdEl = document.getElementById('oicSumReadings');
    if (rdEl) rdEl.textContent = data.length;

    const tmEl = document.getElementById('oicSumTime');
    if (tmEl) tmEl.textContent = last.time ?? '—';

    document.getElementById('oicLiveSummary').style.display = 'flex';
}

// ── OIC History Table ────────────────────────────
function renderOicTable(data) {
    const tbody = document.getElementById('oicTableBody');
    if (!tbody) return;
    tbody.innerHTML = [...data].reverse().map(row => {
        const cc  = row.call_oi_change ?? null;
        const pc  = row.put_oi_change  ?? null;
        const net = (cc ?? 0) + (pc ?? 0);
        const badge = dirClass(row.direction);
        return `<tr>
            <td style="color:#94a3b8;">${row.SNo}</td>
            <td style="color:#64748b;white-space:nowrap;">${row.time}</td>
            <td style="font-weight:700;">${row.index_ltp?.toLocaleString('en-IN') ?? '—'}</td>
            <td style="font-weight:600;color:${chgColor(cc)};">${formatChg(cc)}</td>
            <td style="font-weight:600;color:${chgColor(pc)};">${formatChg(pc)}</td>
            <td style="font-weight:700;color:${chgColor(net)};">${formatChg(net)}</td>
            <td><span class="pcr-dir-badge ${badge}">${row.direction ?? '—'}</span></td>
            <td>
                <button class="pcr-view-btn oic-view-btn"
                        onclick='openOicModal(${JSON.stringify(row)})'>
                    📈 Strikes
                </button>
            </td>
        </tr>`;
    }).join('');
}

// ── Top builders helper ──────────────────────────
function getTopBuilders(strikes) {
    let topCe = null, topPe = null;
    for (const s of strikes) {
        const tag = (s.tag || '').toUpperCase();
        const chg = s.oi_change ?? 0;
        if (tag === 'CE' && (topCe === null || chg > topCe.chg)) topCe = { strike: s.strike, chg };
        if (tag === 'PE' && (topPe === null || chg > topPe.chg)) topPe = { strike: s.strike, chg };
    }
    return { topCe, topPe };
}

// ═══════════════════════════════════════════════
//  OIC — STRIKE OI CHANGE MODAL
// ═══════════════════════════════════════════════

function openOicModal(row) {
    _currentOicRow = row;
    document.getElementById('oicModalTitle').textContent =
        `${row.time}  |  PCR: ${((row.ratio ?? 0) * 100).toFixed(2)}%`;

    switchOicTab(0);

    const strikes = [...(row.strikes || [])].sort((a, b) => (a.strike ?? 0) - (b.strike ?? 0));

    document.getElementById('oicModalBody').innerHTML = strikes.length
        ? strikes.map(s => {
            const cur  = s.open_int  ?? null;
            const bak  = s.backup_oi ?? null;
            const chg  = s.oi_change ?? null;
            const pct  = (bak && chg != null) ? ((chg / bak) * 100).toFixed(2) + '%' : '—';
            const col  = chgColor(chg);
            return `<tr>
                <td style="font-weight:600;">${s.strike ?? '—'}</td>
                <td><span class="tag-${(s.tag || '').toLowerCase()}">${s.tag ?? '—'}</span></td>
                <td style="font-size:11px;color:#64748b;">${s.symbol ?? '—'}</td>
                <td class="num">${formatOI(cur)}</td>
                <td class="num" style="color:#94a3b8;">${formatOI(bak)}</td>
                <td class="num" style="font-weight:700;color:${col};">${formatChg(chg)}</td>
                <td class="num" style="color:${col};">${pct}</td>
            </tr>`;
          }).join('')
        : `<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:20px;">No strike data</td></tr>`;

    document.getElementById('oicModal').style.display = 'flex';
}

function closeOicModal() {
    document.getElementById('oicModal').style.display = 'none';
    _currentOicRow = null;
    if (_oicChart) { _oicChart.destroy(); _oicChart = null; }
}

function switchOicTab(index) {
    const modal = document.getElementById('oicModal');
    modal.querySelectorAll('.ana-modal-tab').forEach((b, i)   => b.classList.toggle('active', i === index));
    modal.querySelectorAll('.ana-modal-tab-panel').forEach((p, i) => p.classList.toggle('active', i === index));
    if (index === 1 && _currentOicRow) renderOicChangeChart(_currentOicRow.strikes || []);
}

// ═══════════════════════════════════════════════
//  OIC — CHANGE BAR CHART  (Chart.js)
// ═══════════════════════════════════════════════

function renderOicChangeChart(strikes) {
    const canvas = document.getElementById('oicChartCanvas');
    if (!canvas) return;

    if (_oicChart) { _oicChart.destroy(); _oicChart = null; }

    // Group by strike ascending
    const map = {};
    for (const s of strikes) {
        const k = s.strike ?? 0;
        if (!map[k]) map[k] = { ce: 0, pe: 0 };
        if ((s.tag || '').toUpperCase() === 'CE') map[k].ce = s.oi_change ?? 0;
        if ((s.tag || '').toUpperCase() === 'PE') map[k].pe = s.oi_change ?? 0;
    }
    const keys = Object.keys(map).map(Number).sort((a, b) => a - b);

    if (!keys.length) {
        canvas.parentElement.innerHTML =
            '<p style="text-align:center;color:#94a3b8;padding:40px;">No OI change data — ensure backend is sending oi_change per strike</p>';
        return;
    }

    // PE = red family, CE = blue family; solid if gained, faded if shed
    const peBg = keys.map(k => map[k].pe >= 0 ? '#fca5a5' : '#fee2e2');
    const peBd = keys.map(k => map[k].pe >= 0 ? '#dc2626' : '#fca5a5');
    const ceBg = keys.map(k => map[k].ce >= 0 ? '#93c5fd' : '#dbeafe');
    const ceBd = keys.map(k => map[k].ce >= 0 ? '#2563eb' : '#93c5fd');

    _oicChart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: keys,
            datasets: [
                {
                    label: 'PE OI Change',
                    data: keys.map(k => map[k].pe),
                    backgroundColor: peBg,
                    borderColor:     peBd,
                    borderWidth: 1.5,
                    borderRadius: 3,
                    order: 1
                },
                {
                    label: 'CE OI Change',
                    data: keys.map(k => map[k].ce),
                    backgroundColor: ceBg,
                    borderColor:     ceBd,
                    borderWidth: 1.5,
                    borderRadius: 3,
                    order: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const v = ctx.parsed.y;
                            return ` ${ctx.dataset.label}: ${v >= 0 ? '+' : ''}${formatOIRaw(v)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(148,163,184,0.12)' },
                    ticks: {
                        font: { size: 10 },
                        color: '#64748b',
                        maxRotation: 45,
                        autoSkip: false
                    }
                },
                y: {
                    grid: { color: 'rgba(148,163,184,0.12)' },
                    border: { dash: [3, 3] },
                    ticks: {
                        font: { size: 11 },
                        color: '#64748b',
                        callback: v => (v >= 0 ? '+' : '') + formatOIRaw(v)
                    }
                }
            }
        }
    });
}

// ═══════════════════════════════════════════════
//  SHARED HELPERS
// ═══════════════════════════════════════════════

function dirClass(direction) {
    if (!direction) return 'unk';
    const k = direction.toLowerCase();
    if (_dirMap[k]) return _dirMap[k];
    // Fallback if config not loaded
    const d = direction.toUpperCase();
    if (d.includes('BEAR') || d.includes('WEAK'))                      return 'bear';
    if (d.includes('BULL'))                                             return 'bull';
    if (d.includes('NEUT') || d.includes('RANGE') || d.includes('MILD')) return 'neut';
    return 'unk';
}

function formatOI(val) {
    if (val == null) return '—';
    const abs = Math.abs(val);
    if (abs >= 1e7) return (val / 1e7).toFixed(2) + ' Cr';
    if (abs >= 1e5) return (val / 1e5).toFixed(2) + ' L';
    return val.toLocaleString('en-IN');
}

// formatOI without '—' fallback — for Chart.js tooltip (val is always a number)
function formatOIRaw(val) {
    const abs = Math.abs(val);
    if (abs >= 1e7) return (val / 1e7).toFixed(2) + ' Cr';
    if (abs >= 1e5) return (val / 1e5).toFixed(2) + ' L';
    return val.toLocaleString('en-IN');
}

function formatChg(val) {
    if (val == null) return '—';
    const prefix = val > 0 ? '+' : '';
    const abs = Math.abs(val);
    if (abs >= 1e7) return prefix + (val / 1e7).toFixed(2) + ' Cr';
    if (abs >= 1e5) return prefix + (val / 1e5).toFixed(2) + ' L';
    return prefix + val.toLocaleString('en-IN');
}

function chgColor(val) {
    if (val == null || val === 0) return '#94a3b8';
    return val > 0 ? '#16a34a' : '#dc2626';
}
