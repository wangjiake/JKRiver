// ── System Stats ─────────────────────────────────────────────────────
let _sysStatsTimer = null;
let _sysStatsInterval = 5000;

async function fetchSysStats() {
  try {
    const r = await fetch(`http://${location.hostname}:${API_PORT}/api/system/stats`, { headers: authHeaders() });
    if (!r.ok) return;
    const d = await r.json();
    if (d.error) return;
    document.getElementById('ssCpu').innerHTML  = `${t('ss_cpu')} ${fmtPct(d.cpu, 70, 90)}`;
    document.getElementById('ssMem').innerHTML  = `${t('ss_mem')} ${fmtPct(d.mem, 75, 90)}`;
    document.getElementById('ssDisk').innerHTML = `${t('ss_disk')} ${fmtPct(d.disk_pct, 80, 95)} <span style="color:var(--text-faint);font-size:10px">· ${d.disk_free_gb}G</span>`;
    document.getElementById('ssNet').innerHTML  = `${t('ss_net')} ↑${fmtSpeed(d.upload_bps)} ↓${fmtSpeed(d.download_bps)}`;
  } catch(e) {}
}

function startSysStats() {
  const el = document.getElementById('sysStats');
  if (el) el.classList.add('visible');
  document.getElementById('sysStatsIntervalRow').style.display = 'flex';
  if (_sysStatsTimer) clearInterval(_sysStatsTimer);
  fetchSysStats();
  _sysStatsTimer = setInterval(fetchSysStats, _sysStatsInterval);
}

function stopSysStats() {
  const el = document.getElementById('sysStats');
  if (el) el.classList.remove('visible');
  document.getElementById('sysStatsIntervalRow').style.display = 'none';
  if (_sysStatsTimer) { clearInterval(_sysStatsTimer); _sysStatsTimer = null; }
}

function onSysStatsChange() {
  const on = document.getElementById('sysStatsToggle').checked;
  localStorage.setItem(SYS_STATS_KEY, on ? '1' : '0');
  on ? startSysStats() : stopSysStats();
}

function onSysStatsIntervalChange() {
  const sel = document.getElementById('sysStatsInterval');
  _sysStatsInterval = parseInt(sel.value, 10);
  localStorage.setItem(SYS_STATS_INTERVAL_KEY, sel.value);
  // Restart timer with new interval if running
  if (_sysStatsTimer) startSysStats();
}

function loadSysStatsSetting() {
  const savedInterval = localStorage.getItem(SYS_STATS_INTERVAL_KEY);
  if (savedInterval) {
    _sysStatsInterval = parseInt(savedInterval, 10);
    const sel = document.getElementById('sysStatsInterval');
    if (sel) sel.value = savedInterval;
  }
  const on = localStorage.getItem(SYS_STATS_KEY) === '1';
  const cb = document.getElementById('sysStatsToggle');
  if (cb) cb.checked = on;
  if (on) startSysStats();
}

loadSysStatsSetting();

// ── Token Usage ──────────────────────────────────────────────────────

async function fetchTokenUsage() {
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/api/token-usage`, { headers: authHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = fmtTokens(val); };
    set('tuBarToday', data.today?.total ?? 0);
    set('tuBarWeek',  data.week?.total  ?? 0);
    set('tuBarMonth', data.month?.total ?? 0);
  } catch (e) {}
}

function onTokenUsageChange() {
  const on = document.getElementById('tokenUsageToggle').checked;
  localStorage.setItem(TOKEN_USAGE_KEY, on ? '1' : '0');
  const bar = document.getElementById('tokenUsageBar');
  if (bar) bar.classList.toggle('visible', on);
  if (on) fetchTokenUsage();
}

function loadTokenUsageSetting() {
  const on = localStorage.getItem(TOKEN_USAGE_KEY) === '1';
  const cb = document.getElementById('tokenUsageToggle');
  if (cb) cb.checked = on;
  const bar = document.getElementById('tokenUsageBar');
  if (bar) bar.classList.toggle('visible', on);
  if (on) fetchTokenUsage();
}

loadTokenUsageSetting();

// ── Task Tray ────────────────────────────────────────────────────────
let _taskTrayExpanded = false;

function toggleTaskTray() {
  _taskTrayExpanded = !_taskTrayExpanded;
  const panel = document.getElementById('taskTrayPanel');
  const btn = document.getElementById('taskTrayToggle');
  panel.classList.toggle('open', _taskTrayExpanded);
  btn.classList.toggle('expanded', _taskTrayExpanded);
  if (_taskTrayExpanded) renderTaskTrayFull();
}

function renderTaskTrayFull() {
  fetch(`http://${location.hostname}:${API_PORT}/api/outsource/tasks`, { headers: authHeaders() })
    .then(r => r.json())
    .then(tasks => {
      const active = tasks.filter(t => ['running','pending','planning'].includes(t.status));
      const cards = document.getElementById('taskTrayCards');
      if (!cards) return;
      cards.innerHTML = '';
      const shown = active.slice(0, 20); // show up to 20, scroll for more
      shown.forEach(task => {
        const a = document.createElement('a');
        a.className = 'task-card';
        a.href = `/outsource#${task.task_id}`;
        const dotClass = task.status === 'running' ? 'running' : task.status === 'done' ? 'done' : 'failed';
        a.innerHTML = `
          <div class="task-card-top">
            <span class="task-card-dot ${dotClass}"></span>
            <span class="task-card-id">#${task.task_id.slice(0,8)}</span>
          </div>
          <div class="task-card-title">${(task.title || '').replace(/</g,'&lt;').slice(0,40)}</div>`;
        cards.appendChild(a);
      });
    }).catch(() => {});
}

function updateTaskBadge() {
  fetch(`http://${location.hostname}:${API_PORT}/api/outsource/tasks/active_count`, { headers: authHeaders() })
    .then(r => r.json())
    .then(data => {
      // Update nav link
      const link = document.getElementById('outsource-nav-link');
      if (link) {
        if (data.count > 0) { link.textContent = `${t('nav_tasks')} (${data.count})`; link.style.color = 'var(--yellow)'; }
        else { link.textContent = t('nav_tasks'); link.style.color = ''; }
      }
      // Update task tray toggle
      const btn = document.getElementById('taskTrayToggle');
      const lbl = document.getElementById('taskTrayLabel');
      if (!btn || !lbl) return;
      if (data.count > 0) {
        lbl.textContent = `⚡ ${data.count}`;
        btn.classList.add('visible');
        if (_taskTrayExpanded) renderTaskTrayFull();
      } else {
        btn.classList.remove('visible');
        // Auto-collapse when no active tasks
        if (_taskTrayExpanded) {
          _taskTrayExpanded = false;
          document.getElementById('taskTrayPanel')?.classList.remove('open');
          btn.classList.remove('expanded');
        }
      }
    }).catch(() => {});
}
updateTaskBadge();
setInterval(updateTaskBadge, 5000);
