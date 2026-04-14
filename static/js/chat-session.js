// ── Sidebar ────────────────────────────────────────────────────────────
function isMobile() { return window.innerWidth <= 768; }

function toggleSidebar() {
  if (isMobile()) {
    sidebarOpen = !sidebarOpen;
    document.getElementById('historySidebar').classList.toggle('open', sidebarOpen);
    document.getElementById('sidebarOverlay').classList.toggle('visible', sidebarOpen);
  } else {
    // Desktop: collapse/expand inline
    const sidebar = document.getElementById('historySidebar');
    const collapsed = sidebar.classList.toggle('collapsed');
    localStorage.setItem(SIDEBAR_KEY, collapsed ? '0' : '1');
  }
}

function closeSidebar() {
  sidebarOpen = false;
  document.getElementById('historySidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('visible');
}

// ── Session list ──────────────────────────────────────────────────────
let allSessions = [];
let pinnedSessions = [];
let sessionOffset = 0;
const SESSION_PAGE = 30;
let sessionHasMore = false;
let searchTimer = null;

async function loadSessionList() {
  sessionOffset = 0;
  allSessions = [];
  try {
    const [pinnedRes, histRes] = await Promise.all([
      fetch(`http://${location.hostname}:${API_PORT}/sessions/pinned`, { headers: authHeaders() }),
      fetch(`http://${location.hostname}:${API_PORT}/sessions?limit=${SESSION_PAGE}&offset=0`, { headers: authHeaders() }),
    ]);
    pinnedSessions = pinnedRes.ok ? await pinnedRes.json() : [];
    if (!histRes.ok) return;
    allSessions = await histRes.json();
    sessionOffset = allSessions.length;
    sessionHasMore = allSessions.length === SESSION_PAGE;
    renderPinnedList(pinnedSessions);
    renderSessionList(allSessions);
    document.getElementById('loadMoreBtn').style.display = sessionHasMore ? '' : 'none';
  } catch(e) { console.warn('Failed to load session list', e); }
}

async function doSearch() {
  clearTimeout(searchTimer);
  const q = document.getElementById('sessionSearch').value;
  if (!q.trim()) {
    renderPinnedList(pinnedSessions);
    renderSessionList(allSessions);
    document.getElementById('loadMoreBtn').style.display = sessionHasMore ? '' : 'none';
    return;
  }
  document.getElementById('loadMoreBtn').style.display = 'none';
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/sessions/search?q=${encodeURIComponent(q)}`, { headers: authHeaders() });
    if (!res.ok) return;
    const results = await res.json();
    renderPinnedList([]);
    renderSessionList(results);
  } catch(e) { console.warn('search failed', e); }
}

function filterSessions(q) {
  clearTimeout(searchTimer);
  if (!q.trim()) {
    renderPinnedList(pinnedSessions);
    renderSessionList(allSessions);
    document.getElementById('loadMoreBtn').style.display = sessionHasMore ? '' : 'none';
    return;
  }
  searchTimer = setTimeout(doSearch, 300);
}

async function loadMoreSessions() {
  const btn = document.getElementById('loadMoreBtn');
  btn.disabled = true;
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/sessions?limit=${SESSION_PAGE}&offset=${sessionOffset}`, { headers: authHeaders() });
    if (!res.ok) return;
    const more = await res.json();
    allSessions = allSessions.concat(more);
    sessionOffset += more.length;
    sessionHasMore = more.length === SESSION_PAGE;
    renderSessionList(allSessions);
    btn.style.display = sessionHasMore ? '' : 'none';
  } catch(e) { console.warn('load more failed', e); }
  btn.disabled = false;
}

function renderSessionItem(s) {
  const title = escHtml(s.custom_name || s.preview || s.session_id.slice(0, 8) + '…');
  const date = s.started_at ? formatDate(s.started_at) : (s.last_at ? formatDate(s.last_at) : '');
  const isActive = s.session_id === sessionId;
  const pinned = s.pinned || false;
  return `<div class="history-item${isActive ? ' active' : ''}" data-sid="${s.session_id}" onclick="switchSession('${s.session_id}')">
    <div class="history-item-content">
      <div class="history-item-title">${title}</div>
      <div class="history-item-time">${date}</div>
    </div>
    <div class="history-item-menu" onclick="showItemMenu(event,'${s.session_id}',${pinned})" title="${t('more')}">⋯</div>
  </div>`;
}

function renderPinnedList(sessions) {
  const wrapper = document.getElementById('pinnedWrapper');
  const list = document.getElementById('pinnedList');
  if (!sessions.length) { wrapper.style.display = 'none'; return; }
  wrapper.style.display = '';
  list.innerHTML = sessions.map(renderSessionItem).join('');
}

function renderSessionList(sessions) {
  const list = document.getElementById('historyList');
  if (!sessions.length) {
    list.innerHTML = `<div class="history-empty">${t('history_empty')}</div>`;
    return;
  }
  list.innerHTML = sessions.map(renderSessionItem).join('');
}

// ── Session actions (pin / rename / delete) ────────────────────────────
let _renameTargetId = null;

function showItemMenu(event, sid, pinned) {
  event.stopPropagation();
  closeDropdown();
  const dd = document.getElementById('itemDropdown');
  dd.innerHTML = `
    <div class="item-dropdown-item" onclick="togglePin('${sid}',${pinned})">${pinned ? t('unpin') : t('pin')}</div>
    <div class="item-dropdown-item" onclick="openRenameModal('${sid}')">${t('rename')}</div>
    <div class="item-dropdown-item danger" onclick="confirmDelete('${sid}')">${t('delete_session')}</div>
  `;
  const rect = event.currentTarget.getBoundingClientRect();
  dd.classList.add('open');
  const ddH = dd.offsetHeight || 96;
  const top = rect.bottom + 4 + ddH > window.innerHeight ? rect.top - ddH - 4 : rect.bottom + 4;
  dd.style.top = top + 'px';
  dd.style.left = Math.max(4, rect.right - 134) + 'px';
}

function closeDropdown() {
  document.getElementById('itemDropdown').classList.remove('open');
}

document.addEventListener('click', closeDropdown);

async function togglePin(sid, currentPinned) {
  closeDropdown();
  try {
    await fetch(`http://${location.hostname}:${API_PORT}/sessions/${sid}/pin`, { method: 'POST', headers: authHeaders() });
    await loadSessionList();
  } catch(e) { console.warn('pin failed', e); }
}

function openRenameModal(sid) {
  closeDropdown();
  _renameTargetId = sid;
  const s = [...pinnedSessions, ...allSessions].find(x => x.session_id === sid);
  document.getElementById('renameInput').value = (s && s.custom_name) ? s.custom_name : '';
  document.getElementById('renameModal').classList.add('open');
  setTimeout(() => document.getElementById('renameInput').focus(), 50);
}

function closeRenameModal() {
  document.getElementById('renameModal').classList.remove('open');
  _renameTargetId = null;
}

async function confirmRename() {
  const sid = _renameTargetId;
  const name = document.getElementById('renameInput').value.trim();
  closeRenameModal();
  if (!sid) return;
  try {
    await fetch(`http://${location.hostname}:${API_PORT}/sessions/${sid}/rename`, {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    await loadSessionList();
  } catch(e) { console.warn('rename failed', e); }
}

async function confirmDelete(sid) {
  closeDropdown();
  if (!confirm(t('delete_confirm'))) return;
  try {
    await fetch(`http://${location.hostname}:${API_PORT}/sessions/${sid}`, { method: 'DELETE', headers: authHeaders() });
    if (sid === sessionId) {
      sessionId = null;
      localStorage.removeItem(STORAGE_KEY);
      document.getElementById('messages').innerHTML = '';
    }
    await loadSessionList();
  } catch(e) { console.warn('delete failed', e); }
}

async function switchSession(sid) {
  if (sid === sessionId) { closeSidebar(); return; }
  if (ws) ws.close();
  sessionId = sid;
  localStorage.setItem(STORAGE_KEY, sid);
  document.getElementById('messages').innerHTML = '';
  document.getElementById('input').disabled = true;
  document.getElementById('sendBtn').disabled = true;
  document.querySelectorAll('.history-item').forEach(el =>
    el.classList.toggle('active', el.dataset.sid === sid));
  closeSidebar();
  await loadHistory(sid);
  connect();
}

function newSession() {
  localStorage.removeItem(STORAGE_KEY); sessionId = null;
  document.getElementById('messages').innerHTML = '';
  document.getElementById('sessionIdDisplay').textContent = '—';
  if (ws) ws.close();
  closeSidebar(); connect(); loadSessionList();
}
