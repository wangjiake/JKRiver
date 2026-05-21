async function load({ silent = false } = {}) {
  const contentEl = document.getElementById('content');
  if (!silent) contentEl.innerHTML = `<div class="loading" id="loading-text">${t('loading')}</div>`;
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/system`, { headers: authHeaders() });
    if (!res.ok) throw new Error(res.status);
    _data = await res.json();
    render(_data);
  } catch(e) {
    document.getElementById('content').innerHTML = `<div class="empty">${t('load_error')}${e.message}</div>`;
  }
}

function showBanner() {
  const b = document.getElementById('restart-banner');
  document.getElementById('banner-msg').textContent = t('banner_msg');
  document.getElementById('btn-restart').textContent = t('btn_restart');
  document.getElementById('btn-revert').textContent = t('btn_revert');
  b.style.display = 'flex';
}
function hideBanner() {
  document.getElementById('restart-banner').style.display = 'none';
}

async function doRestart() {
  const btn = document.getElementById('btn-restart');
  const revertBtn = document.getElementById('btn-revert');
  btn.disabled = revertBtn.disabled = true;
  btn.textContent = t('restarting');
  try {
    await fetch(`http://${location.hostname}:${API_PORT}/system/restart`, {
      method: 'POST', headers: authHeaders(),
    });
  } catch {}
  // Poll until API is back up, max 30 attempts (~30s)
  let attempts = 0;
  const poll = setInterval(async () => {
    attempts++;
    if (attempts > 30) {
      clearInterval(poll);
      btn.disabled = revertBtn.disabled = false;
      btn.textContent = t('btn_restart');
      alert(t('restart_timeout'));
      return;
    }
    try {
      const r = await fetch(`http://${location.hostname}:${API_PORT}/health`);
      if (r.ok) { clearInterval(poll); btn.disabled = revertBtn.disabled = false; btn.textContent = t('btn_restart'); hideBanner(); load(); }
    } catch {}
  }, 1000);
}

async function doRevert() {
  const btn = document.getElementById('btn-revert');
  const restartBtn = document.getElementById('btn-restart');
  btn.disabled = restartBtn.disabled = true;
  btn.textContent = t('reverting');
  try {
    await fetch(`http://${location.hostname}:${API_PORT}/system/revert`, {
      method: 'POST', headers: authHeaders(),
    });
    hideBanner();
    load({ silent: true });
  } catch(e) {
    alert('Failed: ' + e.message);
  } finally {
    btn.disabled = restartBtn.disabled = false;
    btn.textContent = t('btn_revert');
  }
}

// ── Skill Install Modal ───────────────────────────────────────────────

let _installTab = 'paste';

function switchInstallTab(tab) {
  _installTab = tab;
  document.getElementById('tabPaste').classList.toggle('active', tab === 'paste');
  document.getElementById('tabHub').classList.toggle('active', tab === 'hub');
  document.getElementById('paneInstallPaste').classList.toggle('active', tab === 'paste');
  document.getElementById('paneInstallHub').classList.toggle('active', tab === 'hub');
}

function openInstallSkill() {
  document.getElementById('installSkillTitle').textContent = t('install_skill_title');
  document.getElementById('installSkillDesc').textContent = t('install_skill_desc');
  document.getElementById('installSkillYaml').placeholder = t('install_skill_placeholder');
  document.getElementById('tabPaste').textContent = t('tab_paste');
  document.getElementById('tabHub').textContent = t('tab_hub');
  document.getElementById('hubDesc').textContent = t('hub_desc');
  document.getElementById('hubFetchBtn').textContent = t('hub_search_btn');
  document.getElementById('installCancelBtn').textContent = t('btn_cancel');
  document.getElementById('installConfirmBtn').textContent = t('btn_install');
  document.getElementById('hubCancelBtn').textContent = t('btn_cancel');
  document.getElementById('installSkillYaml').value = '';
  document.getElementById('hubSkillName').value = '';
  document.getElementById('hubStatus').textContent = '';
  document.getElementById('hubStatus').className = 'hub-status';
  switchInstallTab('paste');
  document.getElementById('installSkillModal').classList.add('open');
  setTimeout(() => document.getElementById('installSkillYaml').focus(), 50);
}
function closeInstallSkill() {
  document.getElementById('installSkillModal').classList.remove('open');
}
async function doInstallSkill() {
  const content = document.getElementById('installSkillYaml').value.trim();
  if (!content) return;
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/system/skill/install`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    const data = await res.json();
    if (!res.ok) { alert('Failed: ' + (data.detail || res.status)); return; }
    closeInstallSkill();
    load({ silent: true });
  } catch(e) { alert('Error: ' + e.message); }
}
async function doFetchFromHub() {
  const name = document.getElementById('hubSkillName').value.trim();
  if (!name) return;
  // If user pasted SKILL.md content instead of a skill name, redirect to paste tab
  if (name.startsWith('---')) {
    document.getElementById('installSkillYaml').value = name;
    switchInstallTab('paste');
    return;
  }
  const statusEl = document.getElementById('hubStatus');
  statusEl.textContent = t('hub_searching');
  statusEl.className = 'hub-status';
  document.getElementById('hubFetchBtn').disabled = true;
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/system/skill/install-from-hub`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    const data = await res.json();
    if (!res.ok) {
      statusEl.textContent = data.detail || t('hub_not_found');
      statusEl.className = 'hub-status err';
    } else {
      statusEl.textContent = '✓ ' + data.name;
      statusEl.className = 'hub-status ok';
      setTimeout(() => { closeInstallSkill(); load({ silent: true }); }, 800);
    }
  } catch(e) {
    statusEl.textContent = e.message;
    statusEl.className = 'hub-status err';
  }
  document.getElementById('hubFetchBtn').disabled = false;
}
document.getElementById('hubSkillName').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') doFetchFromHub();
});
document.getElementById('installSkillModal').addEventListener('click', function(e) {
  if (e.target === this) closeInstallSkill();
});

// ── Theme ──────────────────────────────────────────────────────────────
const _SVG_MOON = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
const _SVG_SUN  = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
function updateThemeBtn() {
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.innerHTML = document.body.classList.contains('light') ? _SVG_MOON : _SVG_SUN;
}
(function() {
  const saved = localStorage.getItem('theme') || 'dark';
  if (saved === 'light') {
    document.body.classList.add('light');
    document.documentElement.classList.add('light');
  }
  updateThemeBtn();
})();


function toggleTheme() {
  const isLight = document.body.classList.toggle('light');
  document.documentElement.classList.toggle('light', isLight);
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
  updateThemeBtn();
}

// ── Init ───────────────────────────────────────────────────────────────
document.querySelectorAll('.lang-btn').forEach(b =>
  b.classList.toggle('active', b.textContent === { zh:'中文', en:'EN', ja:'日本語' }[currentLang]));
document.getElementById('nav-chat').textContent = t('nav_chat');
document.getElementById('nav-profile').textContent = t('nav_profile');
const _outNavBtn = document.getElementById('outsource-nav-link');
if (_outNavBtn) _outNavBtn.textContent = t('nav_tasks');
document.getElementById('nav-system').textContent = t('nav_system');
document.getElementById('header-title').textContent = '⚙ ' + t('nav_system');
document.title = t('nav_system') + ' — ' + DB_NAME;
load();
