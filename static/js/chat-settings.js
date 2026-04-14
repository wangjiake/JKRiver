// ── Status ────────────────────────────────────────────────────────────
function setStatus(state, text) {
  document.getElementById('statusDot').className = 'status-dot' + (state ? ' ' + state : '');
  document.getElementById('statusText').textContent = text;
}

// ── Settings ──────────────────────────────────────────────────────────
function toggleSettings() {
  settingsOpen = !settingsOpen;
  document.getElementById('settingsPanel').classList.toggle('open', settingsOpen);
  document.getElementById('settingsBtn').classList.toggle('active', settingsOpen);
  if (settingsOpen) {
    closeSidebar();
    if (window.innerWidth <= 768) document.getElementById('sidebarOverlay').classList.add('visible');
  } else {
    document.getElementById('sidebarOverlay').classList.remove('visible');
  }
}

// ── Sleep ─────────────────────────────────────────────────────────────
async function runSleep() {
  const btn = document.getElementById('sleepBtn');
  const status = document.getElementById('sleepStatus');
  btn.disabled = true; btn.className = 'sleep-btn running'; btn.textContent = t('sleep_running_btn');
  status.className = 'sleep-status running'; status.textContent = t('sleep_running');
  setStatus('sleeping', t('sleeping_status'));
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/sleep`, { method: 'POST', headers: authHeaders() });
    if (res.ok) {
      btn.className = 'sleep-btn success'; btn.textContent = t('sleep_success_btn');
      status.className = 'sleep-status success'; status.textContent = t('sleep_success');
      setStatus('connected', t('connected'));
      setTimeout(() => { btn.className = 'sleep-btn'; btn.textContent = t('sleep_btn'); btn.disabled = false; status.className = 'sleep-status'; }, 4000);
    } else { throw new Error(); }
  } catch {
    btn.className = 'sleep-btn'; btn.textContent = t('sleep_btn'); btn.disabled = false;
    status.className = 'sleep-status error'; status.textContent = t('sleep_error');
    setStatus('connected', t('connected'));
  }
}

let scheduleMode = localStorage.getItem(SLEEP_MODE_KEY) || 'interval';
function setScheduleMode(mode) {
  scheduleMode = mode; localStorage.setItem(SLEEP_MODE_KEY, mode);
  document.getElementById('modeInterval').classList.toggle('active', mode === 'interval');
  document.getElementById('modeDaily').classList.toggle('active', mode === 'daily');
  document.getElementById('intervalConfig').style.display = mode === 'interval' ? '' : 'none';
  document.getElementById('dailyConfig').style.display = mode === 'daily' ? '' : 'none';
  if (document.getElementById('autoSleepToggle').checked) startAutoSleep();
}
function saveScheduleConfig() {
  localStorage.setItem(SLEEP_INTERVAL_KEY, document.getElementById('intervalHours').value);
  localStorage.setItem(SLEEP_TIME_KEY, document.getElementById('dailyTime').value);
  if (document.getElementById('autoSleepToggle').checked) startAutoSleep();
}
function loadAutoSleepSetting() {
  const enabled = localStorage.getItem(AUTO_SLEEP_KEY) === 'true';
  document.getElementById('autoSleepToggle').checked = enabled;
  document.getElementById('intervalHours').value = localStorage.getItem(SLEEP_INTERVAL_KEY) || '1';
  document.getElementById('dailyTime').value = localStorage.getItem(SLEEP_TIME_KEY) || '02:00';
  setScheduleMode(scheduleMode);
  document.getElementById('scheduleConfig').style.display = enabled ? '' : 'none';
  updateNextRunLabel();
  if (enabled) startAutoSleep();
}
function onAutoSleepChange() {
  const enabled = document.getElementById('autoSleepToggle').checked;
  localStorage.setItem(AUTO_SLEEP_KEY, enabled);
  document.getElementById('scheduleConfig').style.display = enabled ? '' : 'none';
  if (enabled) { startAutoSleep(); } else { clearTimeout(autoSleepTimer); autoSleepTimer = null; document.getElementById('autoSleepSub').textContent = ''; }
}
function startAutoSleep() {
  clearTimeout(autoSleepTimer);
  updateNextRunLabel();
  autoSleepTimer = setTimeout(() => {
    runSleep().then(() => { if (document.getElementById('autoSleepToggle').checked) startAutoSleep(); });
  }, msUntilNextRun());
}
function msUntilNextRun() {
  if (scheduleMode === 'interval') return (parseFloat(document.getElementById('intervalHours').value) || 1) * 3600000;
  const [hh, mm] = (document.getElementById('dailyTime').value || '02:00').split(':').map(Number);
  const now = new Date(), next = new Date(now);
  next.setHours(hh, mm, 0, 0);
  if (next <= now) next.setDate(next.getDate() + 1);
  return next - now;
}
function updateNextRunLabel() {
  const sub = document.getElementById('autoSleepSub');
  if (!document.getElementById('autoSleepToggle').checked) { sub.textContent = ''; return; }
  if (scheduleMode === 'interval') {
    sub.textContent = t('next_interval', { m: Math.round((parseFloat(document.getElementById('intervalHours').value) || 1) * 60) });
  } else {
    const time = document.getElementById('dailyTime').value || '02:00';
    const [hh, mm] = time.split(':').map(Number);
    const now = new Date(), next = new Date(now);
    next.setHours(hh, mm, 0, 0);
    sub.textContent = t(next <= now ? 'next_daily_tomorrow' : 'next_daily', { time });
  }
}

// ── Theme ──────────────────────────────────────────────────────────────
const _SVG_MOON = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
const _SVG_SUN  = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
function updateThemeBtn() {
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.innerHTML = document.body.classList.contains('light') ? _SVG_MOON : _SVG_SUN;
}
(function() {
  const saved = localStorage.getItem('theme') || 'dark';
  if (saved === 'light') document.body.classList.add('light');
  updateThemeBtn();
})();

function toggleTheme() {
  const isLight = document.body.classList.toggle('light');
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
  updateThemeBtn();
}

// ── Init ──────────────────────────────────────────────────────────────
async function init() {
  setLang(currentLang);
  // Restore sidebar state on desktop
  if (!isMobile()) {
    const saved = localStorage.getItem(SIDEBAR_KEY);
    if (saved === '0') document.getElementById('historySidebar').classList.add('collapsed');
  }
  // Hide voice button if browser doesn't support Web Speech API
  if (!window.SpeechRecognition && !window.webkitSpeechRecognition) {
    document.getElementById('voiceBtn').style.display = 'none';
  }
  // Check backend capabilities and hide unsupported buttons
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/capabilities`, { headers: authHeaders() });
    if (res.ok) {
      const cap = await res.json();
      if (!cap.image) document.getElementById('imageInputBtn').style.display = 'none';
      // voice button: hide if neither browser nor backend supports it
      if (!cap.voice && !window.SpeechRecognition && !window.webkitSpeechRecognition) {
        document.getElementById('voiceBtn').style.display = 'none';
      }
    }
  } catch {
    // API unreachable — keep buttons visible, errors handled at send time
  }
  loadAutoSleepSetting();
  await loadSessionList();
  if (sessionId) await loadHistory(sessionId);
  connect();
}

// ── Input events ──────────────────────────────────────────────────────
document.getElementById('input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); sendMessage(); }
});
document.getElementById('input').addEventListener('input', function () {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 140) + 'px';
});

init();

document.addEventListener('DOMContentLoaded', function() {
  var msgs = document.querySelector('.messages');
  if (msgs) {
  }
});
