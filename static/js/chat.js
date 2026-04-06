const API_PORT = 8400;
const STORAGE_KEY = 'jkriver_session_id';
const TOKEN_COOKIE = 'jkriver_token';

function getDeviceToken() {
    const match = document.cookie.match(/(?:^|;\s*)jkriver_token=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : '';
}

function localISOTime() {
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    const off = -now.getTimezoneOffset();
    const sign = off >= 0 ? '+' : '-';
    const hh = pad(Math.floor(Math.abs(off) / 60));
    const mm = pad(Math.abs(off) % 60);
    return `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}${sign}${hh}:${mm}`;
}

function authHeaders(extra) {
    const token = getDeviceToken();
    const h = { 'Content-Type': 'application/json', ...(extra || {}) };
    if (token) h['X-Device-Token'] = token;
    return h;
}
const AUTO_SLEEP_KEY = 'jkriver_auto_sleep';
const SLEEP_MODE_KEY = 'jkriver_sleep_mode';
const SLEEP_INTERVAL_KEY = 'jkriver_sleep_hours';
const SLEEP_TIME_KEY = 'jkriver_sleep_time';
const LANG_KEY = 'jkriver_lang';
const SIDEBAR_KEY = 'jkriver_sidebar_open';

let ws = null;
let sessionId = localStorage.getItem(STORAGE_KEY) || null;
let waiting = false;
let autoSleepTimer = null;
const _pendingTaskQuestions = new Map();  // taskId -> { taskId, taskIdShort, question }
let settingsOpen = false;
let sidebarOpen = false;
let pendingImage = null; // { file, dataUrl }
let recognition = null;
let isRecording = false;

// ── i18n ──────────────────────────────────────────────────────────────
const I18N = {
  zh: {
    title: 'Chat', nav_chat: '聊天', nav_profile: '个人资料', nav_tasks: '外包', nav_system: '系统', settings_title: '设置',
    section_sleep: '睡眠', auto_sleep: '定时睡眠',
    mode_interval: '间隔', mode_daily: '定时',
    every_label: '每', hours_label: '小时运行一次',
    at_label: '每天', daily_suffix: '执行',
    sleep_btn: '立即执行睡眠', sleep_running: '⏳ 记忆整合中…', sleep_success: '✓ 记忆整合完成', sleep_error: '✗ 睡眠失败，请查看日志',
    sleep_running_btn: '睡眠中…', sleep_success_btn: '完成 ✓',
    section_session: '会话', session_label: '当前会话 ID', new_session: '新建会话',
    connecting: '连接中…', connected: '已连接', disconnected: '已断开 — 刷新页面重连',
    sleeping_status: '睡眠运行中…',
    history_divider: '— 上次会话 {n} 条消息 —',
    placeholder: '输入消息…', send: '发送', stop: '停止',
    outsource_task: '外包', task_done: '执行完成', task_failed: '执行失败',
    confirm_start: '✅ 确认开始', cancel_task: '❌ 取消',
    task_starting: '启动中…', task_running: '后台执行中', task_cancelled: '已取消',
    task_question_label: '需要确认', task_question_placeholder: '输入回复…', task_question_send: '回复', task_question_answered: '已回复',
    hint: 'Ctrl+Enter 发送 · Enter 换行',
    next_interval: '下次运行：{m} 分钟后',
    next_daily: '下次运行：今天 {time}',
    next_daily_tomorrow: '下次运行：明天 {time}',
    history_title: '历史会话', new_chat: '+ 新建',
    history_empty: '暂无历史会话', turns_unit: '条',
    attach_title: '附加图片', voice_title: '语音输入',
    voice_no_support: '浏览器不支持语音输入',
    uploading: '上传中…',
    search_placeholder: '搜索…', load_more: '↓ 加载更多', more: '更多',
    pinned_label: '置顶', history_label: '历史记录', pin: '置顶', unpin: '取消置顶',
    rename: '重命名', delete_session: '删除',
    rename_title: '重命名会话', rename_placeholder: '输入名称…',
    btn_cancel: '取消', btn_save: '保存',
    delete_confirm: '确定删除这个会话？',
    section_sys_stats: '系统状态', sys_stats_label: '状态栏显示系统信息', sys_stats_sub: '显示 CPU / 内存 / 硬盘 / 网速', sys_stats_interval: '刷新间隔',
    ss_cpu: 'CPU', ss_mem: '内存', ss_disk: '磁盘', ss_net: '网络',
    section_token_usage: 'Token 用量', token_today: '今天', token_week: '本周', token_month: '本月',
    token_usage_label: '状态栏显示 Token 用量', token_usage_sub: '今天 / 本周 / 本月',
  },
  en: {
    title: 'Chat', nav_chat: 'Chat', nav_profile: 'Profile', nav_tasks: 'Tasks', nav_system: 'System', settings_title: 'Settings',
    section_sleep: 'Sleep', auto_sleep: 'Auto Sleep',
    mode_interval: 'Interval', mode_daily: 'Daily',
    every_label: 'Every', hours_label: 'hour(s)',
    at_label: 'At', daily_suffix: '',
    sleep_btn: 'Run Sleep Now', sleep_running: '⏳ Memory consolidation running…', sleep_success: '✓ Memory consolidation complete', sleep_error: '✗ Sleep failed — check API logs',
    sleep_running_btn: 'Sleeping…', sleep_success_btn: 'Complete ✓',
    section_session: 'Session', session_label: 'Current session ID', new_session: 'New Session',
    connecting: 'Connecting…', connected: 'Connected', disconnected: 'Disconnected — reload to reconnect',
    sleeping_status: 'Sleep running…',
    history_divider: '— {n} messages from previous session —',
    placeholder: 'Type a message…', send: 'Send', stop: 'Stop',
    outsource_task: 'Task', task_done: 'Completed', task_failed: 'Failed',
    confirm_start: '✅ Start', cancel_task: '❌ Cancel',
    task_starting: 'Starting…', task_running: 'Running in background', task_cancelled: 'Cancelled',
    task_question_label: 'Needs input', task_question_placeholder: 'Type your reply…', task_question_send: 'Reply', task_question_answered: 'Answered',
    hint: 'Ctrl+Enter to send · Enter for new line',
    next_interval: 'Next run in {m} min',
    next_daily: 'Next: today at {time}',
    next_daily_tomorrow: 'Next: tomorrow at {time}',
    history_title: 'History', new_chat: '+ New',
    history_empty: 'No history yet', turns_unit: 'msgs',
    attach_title: 'Attach image', voice_title: 'Voice input',
    voice_no_support: 'Voice input not supported in this browser',
    uploading: 'Uploading…',
    search_placeholder: 'Search…', load_more: '↓ Load more', more: 'More',
    pinned_label: 'Pinned', history_label: 'History', pin: 'Pin', unpin: 'Unpin',
    rename: 'Rename', delete_session: 'Delete',
    rename_title: 'Rename Session', rename_placeholder: 'Enter name…',
    btn_cancel: 'Cancel', btn_save: 'Save',
    delete_confirm: 'Delete this session?',
    section_sys_stats: 'System Stats', sys_stats_label: 'Show system info in status bar', sys_stats_sub: 'CPU / Memory / Disk / Network speed', sys_stats_interval: 'Refresh interval',
    ss_cpu: 'CPU', ss_mem: 'Memory', ss_disk: 'Disk', ss_net: 'Network',
    section_token_usage: 'Token Usage', token_today: 'Today', token_week: 'Week', token_month: 'Month',
    token_usage_label: 'Show token usage in status bar', token_usage_sub: 'Today / This week / This month',
  },
  ja: {
    title: 'チャット', nav_chat: 'チャット', nav_profile: 'プロフィール', nav_tasks: '派遣', nav_system: 'システム', settings_title: '設定',
    section_sleep: 'スリープ', auto_sleep: '自動スリープ',
    mode_interval: '間隔', mode_daily: '毎日',
    every_label: '毎', hours_label: '時間ごと',
    at_label: '毎日', daily_suffix: 'に実行',
    sleep_btn: '今すぐスリープ実行', sleep_running: '⏳ 記憶統合中…', sleep_success: '✓ 記憶統合完了', sleep_error: '✗ スリープ失敗 — ログを確認',
    sleep_running_btn: 'スリープ中…', sleep_success_btn: '完了 ✓',
    section_session: 'セッション', session_label: '現在のセッション ID', new_session: '新しいセッション',
    connecting: '接続中…', connected: '接続済み', disconnected: '切断 — リロードして再接続',
    sleeping_status: 'スリープ実行中…',
    history_divider: '— 前回セッション {n} 件のメッセージ —',
    placeholder: 'メッセージを入力…', send: '送信', stop: '停止',
    outsource_task: 'タスク', task_done: '完了', task_failed: '失敗',
    confirm_start: '✅ 開始', cancel_task: '❌ キャンセル',
    task_starting: '開始中…', task_running: 'バックグラウンド実行中', task_cancelled: 'キャンセル済み',
    hint: 'Ctrl+Enter で送信 · Enter で改行',
    next_interval: '次回実行：{m} 分後',
    next_daily: '次回：本日 {time}',
    next_daily_tomorrow: '次回：明日 {time}',
    history_title: '履歴', new_chat: '+ 新規',
    history_empty: '履歴がありません', turns_unit: '件',
    attach_title: '画像を添付', voice_title: '音声入力',
    voice_no_support: 'このブラウザは音声入力に対応していません',
    uploading: 'アップロード中…',
    search_placeholder: '検索…', load_more: '↓ もっと読む', more: 'その他',
    pinned_label: 'ピン留め', history_label: '履歴', pin: 'ピン留め', unpin: 'ピン解除',
    rename: '名前を変更', delete_session: '削除',
    rename_title: 'セッション名変更', rename_placeholder: '名前を入力…',
    btn_cancel: 'キャンセル', btn_save: '保存',
    delete_confirm: 'このセッションを削除しますか？',
    section_sys_stats: 'システム状態', sys_stats_label: 'ステータスバーにシステム情報を表示', sys_stats_sub: 'CPU / メモリ / ディスク / 通信速度', sys_stats_interval: '更新間隔',
    ss_cpu: 'CPU', ss_mem: 'メモリ', ss_disk: 'ディスク', ss_net: 'ネットワーク',
    section_token_usage: 'Token 使用量', token_today: '今日', token_week: '今週', token_month: '今月',
    token_usage_label: 'ステータスバーにToken使用量を表示', token_usage_sub: '今日 / 今週 / 今月',
  },
};

function detectLang() {
  const saved = localStorage.getItem(LANG_KEY);
  if (saved && I18N[saved]) return saved;
  const lang = (navigator.language || 'en').toLowerCase();
  if (lang.startsWith('zh')) return 'zh';
  if (lang.startsWith('ja')) return 'ja';
  return 'en';
}
let currentLang = detectLang();

function t(key, params) {
  let s = (I18N[currentLang] || I18N.en)[key] || key;
  if (params) { for (const [k, v] of Object.entries(params)) s = s.replace(`{${k}}`, v); }
  return s;
}

// ── System Stats ─────────────────────────────────────────────────────────────
const SYS_STATS_KEY = 'jkriver_sys_stats';
const SYS_STATS_INTERVAL_KEY = 'jkriver_sys_stats_interval';
let _sysStatsTimer = null;
let _sysStatsInterval = 5000;

function fmtSpeed(bps) {
  if (bps >= 1024 * 1024) return (bps / 1024 / 1024).toFixed(1) + 'M';
  if (bps >= 1024) return (bps / 1024).toFixed(0) + 'K';
  return bps + 'B';
}

function fmtPct(v, warnAt=70, critAt=90) {
  const cls = v >= critAt ? 'sys-stat-crit' : v >= warnAt ? 'sys-stat-warn' : '';
  return `<span class="${cls}">${v}%</span>`;
}

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

const TOKEN_USAGE_KEY = 'jkriver_token_usage';

function fmtTokens(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return String(n);
}

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

function setLang(lang) {
  currentLang = lang;
  localStorage.setItem(LANG_KEY, lang);
  const labels = { zh: '中文', en: 'EN', ja: '日本語' };
  document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.textContent.trim() === labels[lang]));
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (I18N[lang][key]) el.textContent = I18N[lang][key];
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    if (I18N[lang][key]) el.placeholder = I18N[lang][key];
  });
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.dataset.i18nTitle;
    if (I18N[lang][key]) el.title = I18N[lang][key];
  });
  const dot = document.getElementById('statusDot');
  if (dot.classList.contains('connected')) setStatus('connected', t('connected'));
  else if (dot.classList.contains('error')) setStatus('error', t('disconnected'));
  updateNextRunLabel();
}

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

// ── Image attachment ───────────────────────────────────────────────────
function triggerImagePicker() {
  document.getElementById('imageInput').click();
}

function onImageSelected(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    pendingImage = { file, dataUrl: e.target.result };
    document.getElementById('attachmentThumb').src = e.target.result;
    document.getElementById('attachmentName').textContent = file.name;
    document.getElementById('attachmentPreview').style.display = 'flex';
  };
  reader.readAsDataURL(file);
  input.value = '';
}

function clearAttachment() {
  pendingImage = null;
  document.getElementById('attachmentPreview').style.display = 'none';
  document.getElementById('attachmentThumb').src = '';
}

// ── Voice input ────────────────────────────────────────────────────────
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

function toggleVoice() {
  if (!SpeechRecognition) { alert(t('voice_no_support')); return; }
  if (isRecording) {
    stopVoice();
  } else {
    startVoice();
  }
}

function startVoice() {
  recognition = new SpeechRecognition();
  const langMap = { zh: 'zh-CN', en: 'en-US', ja: 'ja-JP' };
  recognition.lang = langMap[currentLang] || 'zh-CN';
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onresult = (e) => {
    const text = e.results[0][0].transcript;
    const input = document.getElementById('input');
    input.value = (input.value ? input.value + ' ' : '') + text;
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 140) + 'px';
  };
  recognition.onend = () => stopVoice();
  recognition.onerror = () => stopVoice();

  recognition.start();
  isRecording = true;
  document.getElementById('voiceBtn').classList.add('recording');
}

function stopVoice() {
  if (recognition) { try { recognition.stop(); } catch(e) {} recognition = null; }
  isRecording = false;
  document.getElementById('voiceBtn').classList.remove('recording');
}

// ── Send message ───────────────────────────────────────────────────────
function setSendStopMode(isStop) {
  const btn = document.getElementById('sendBtn');
  if (isStop) {
    btn.classList.add('stop-mode');
    btn.disabled = false;
  } else {
    btn.classList.remove('stop-mode');
  }
}

function stopResponse() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'cancel' }));
  waiting = false;
  setSendStopMode(false);
  document.getElementById('sendBtn').disabled = false;
  removeThinking();
}

function handleSendStop() {
  if (waiting) stopResponse();
  else sendMessage();
}

async function sendMessage() {
  const input = document.getElementById('input');
  const text = input.value.trim();
  if ((!text && !pendingImage) || waiting) return;

  // If any task is waiting for user input, route to task_answer instead of LLM
  if (_pendingTaskQuestions.size > 0 && text && !pendingImage) {
    // Route to the most recent pending question
    const latest = [..._pendingTaskQuestions.values()].at(-1);
    input.value = '';
    input.style.height = 'auto';
    appendMessage('user', text, '', '');
    submitTaskAnswer(latest.taskId, latest.taskIdShort, text);
    return;
  }

  if (pendingImage) {
    await sendImageMessage(text);
    return;
  }

  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  appendMessage('user', text, '', '');
  ws.send(JSON.stringify({ message: text, client_time: localISOTime() }));
  input.value = '';
  input.style.height = 'auto';
  waiting = true;
  document.getElementById('sendBtn').disabled = false;
  setSendStopMode(true);
  showThinking();
}

async function sendImageMessage(caption) {
  const input = document.getElementById('input');
  const file = pendingImage.file;
  const dataUrl = pendingImage.dataUrl;

  // Show user message with image
  appendImageMessage('user', dataUrl, caption);
  input.value = '';
  input.style.height = 'auto';
  clearAttachment();
  waiting = true;
  setSendStopMode(true);
  showThinking();

  try {
    // Upload file
    const formData = new FormData();
    formData.append('file', file);
    const uploadHeaders = {};
    const tok = getDeviceToken();
    if (tok) uploadHeaders['X-Device-Token'] = tok;
    const upRes = await fetch(`http://${location.hostname}:${API_PORT}/upload`, {
      method: 'POST', body: formData, headers: uploadHeaders,
    });
    if (!upRes.ok) throw new Error('Upload failed');
    const { file_path } = await upRes.json();

    // Send via REST /chat
    const chatRes = await fetch(`http://${location.hostname}:${API_PORT}/chat`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        message: caption,
        session_id: sessionId,
        input_type: 'image',
        file_path,
        client_time: localISOTime(),
      }),
    });
    if (!chatRes.ok) throw new Error('Chat failed');
    const result = await chatRes.json();
    removeThinking();
    waiting = false;
    document.getElementById('sendBtn').disabled = false;
    appendMessage('agent', result.response, result.category, result.intent);
  } catch(e) {
    removeThinking();
    waiting = false;
    document.getElementById('sendBtn').disabled = false;
    appendMessage('agent', '⚠ ' + e.message, 'error', '');
  }
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

function formatDate(iso) {
  const d = new Date(iso), now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);
  if (diffDays === 0) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diffDays === 1) return currentLang === 'zh' ? '昨天' : currentLang === 'ja' ? '昨日' : 'Yesterday';
  if (diffDays < 7) return `${diffDays}${currentLang === 'zh' ? '天前' : currentLang === 'ja' ? '日前' : 'd ago'}`;
  const sameYear = d.getFullYear() === now.getFullYear();
  if (sameYear) return `${d.getMonth()+1}/${d.getDate()}`;
  return currentLang === 'zh'
    ? `${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()}`
    : currentLang === 'ja'
    ? `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日`
    : `${d.getMonth()+1}/${d.getDate()}/${d.getFullYear()}`;
}

function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

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

// ── WebSocket ─────────────────────────────────────────────────────────
function connect() {
  const tok = getDeviceToken();
  const tokenParam = tok ? `&token=${encodeURIComponent(tok)}` : '';
  const url = sessionId
    ? `ws://${location.hostname}:${API_PORT}/ws/chat?session_id=${sessionId}${tokenParam}`
    : `ws://${location.hostname}:${API_PORT}/ws/chat${tok ? '?token=' + encodeURIComponent(tok) : ''}`;
  ws = new WebSocket(url);
  ws.onopen = () => setStatus('connected', t('connected'));
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'session_created') {
      const isNew = !sessionId || sessionId !== data.session_id;
      sessionId = data.session_id;
      localStorage.setItem(STORAGE_KEY, sessionId);
      document.getElementById('sessionIdDisplay').textContent = sessionId;
      document.getElementById('input').disabled = false;
      document.getElementById('sendBtn').disabled = false;
      document.getElementById('input').focus();
      if (isNew) loadSessionList();
      // Recover any pending task questions (e.g. after page refresh)
      recoverPendingTaskQuestions();
      return;
    }
    // Background task events must NOT reset waiting/thinking state
    const _bgTypes = new Set(['outsource_started','outsource_cancelled','task_complete','task_question']);
    if (!_bgTypes.has(data.type)) {
      removeThinking();
      waiting = false;
      setSendStopMode(false);
      document.getElementById('sendBtn').disabled = false;
    }
    if (data.type === 'response') appendMessage('agent', data.response, data.category, data.intent);
    else if (data.type === 'cancelled') { /* silently reset — user already saw stop */ }
    else if (data.type === 'outsource_started') {
      updateTaskActions(data.task_id, 'running');
      return;
    }
    else if (data.type === 'outsource_cancelled') {
      updateTaskActions(data.task_id, 'failed');
      return;
    }
    else if (data.type === 'task_complete') {
      updateTaskActions(data.task_id, data.success ? 'done' : 'failed', data.result, data.files_changed, data.steps_count);
      const _Lt = I18N[currentLang] || {};
      const icon = data.success ? '✅' : '❌';
      const label = data.success ? (_Lt.task_done || '执行完成') : (_Lt.task_failed || '执行失败');
      showToast(`${icon} Task #${data.task_id_short} ${label}`, data.success);
      return;
    }
    else if (data.type === 'task_question') {
      _pendingTaskQuestions.set(data.task_id, { taskId: data.task_id, taskIdShort: data.task_id_short, question: data.question });
      appendTaskQuestion(data.task_id, data.task_id_short, data.question);
      return;
    }
    else if (data.type === 'error') appendMessage('agent', '⚠ ' + data.detail, 'error', '');
  };
  ws.onclose = () => {
    setStatus('error', t('disconnected'));
    document.getElementById('input').disabled = true;
    document.getElementById('sendBtn').disabled = true;
  };
  ws.onerror = () => setStatus('error', t('disconnected'));
}

// ── History ───────────────────────────────────────────────────────────
async function loadHistory(sid) {
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/session/${sid}/history`, { headers: authHeaders() });
    if (!res.ok) return;
    const history = await res.json();
    if (!history.length) return;
    const container = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = 'history-divider';
    div.textContent = t('history_divider', { n: history.length });
    container.appendChild(div);
    history.forEach(item => {
      if (item.user) appendMessage('user', item.user, '', '', item.at, true);
      if (item.agent) appendMessage('agent', item.agent, '', '', item.at, true);
    });
  } catch(e) { console.warn('Failed to load history', e); }
}

// ── Recover pending task questions after refresh ───────────────────────
async function recoverPendingTaskQuestions() {
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/api/outsource/tasks`, { headers: authHeaders() });
    if (!res.ok) return;
    const tasks = await res.json();
    for (const task of tasks) {
      if (task.status === 'running' && task.pending_question) {
        // Skip if already shown
        if (_pendingTaskQuestions.has(task.task_id)) continue;
        if (document.querySelector(`[data-task-question-id="${task.task_id}"]`)) continue;
        const shortId = task.task_id.slice(0, 8);
        _pendingTaskQuestions.set(task.task_id, { taskId: task.task_id, taskIdShort: shortId, question: task.pending_question });
        appendTaskQuestion(task.task_id, shortId, task.pending_question);
      }
    }
  } catch(e) { console.warn('Failed to recover task questions', e); }
}

// ── Messages ──────────────────────────────────────────────────────────
function appendTaskQuestion(taskId, taskIdShort, question) {
  const container = document.getElementById('messages');
  const _L = I18N[currentLang] || {};

  // Remove any previous unanswered bubble from the same task to avoid duplicate IDs
  document.querySelectorAll(`[data-task-question-id="${taskId}"]`).forEach(el => el.remove());

  // Use a unique input ID per question to avoid collisions across multiple asks
  const inputId = `tq-input-${taskId}-${Date.now()}`;

  const div = document.createElement('div');
  div.className = 'msg agent';
  div.dataset.taskQuestionId = taskId;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  const qDiv = document.createElement('div');
  qDiv.className = 'task-question';
  qDiv.innerHTML = `
    <div class="task-question-label">🤖 Task #${taskIdShort} — ${_L.task_question_label || '需要确认'}</div>
    <div class="task-question-text">${question.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>
    <div class="task-question-input">
      <textarea rows="2" id="${inputId}" placeholder="${_L.task_question_placeholder || '输入回复…'}" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();submitTaskAnswer('${taskId}','${taskIdShort}','${inputId}');}"></textarea>
      <button onclick="submitTaskAnswer('${taskId}', '${taskIdShort}', '${inputId}')">${_L.task_question_send || '回复'}</button>
    </div>`;

  bubble.appendChild(qDiv);
  div.appendChild(bubble);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;

  setTimeout(() => {
    const inp = document.getElementById(inputId);
    if (inp) inp.focus();
  }, 100);
}

function submitTaskAnswer(taskId, taskIdShort, inputIdOrAnswer) {
  // inputIdOrAnswer: either the unique input element ID (from button click) or the answer text (from main chat input)
  let answer;
  if (inputIdOrAnswer && inputIdOrAnswer.startsWith('tq-input-')) {
    const inp = document.getElementById(inputIdOrAnswer);
    if (!inp) return;
    answer = inp.value.trim();
  } else {
    answer = (inputIdOrAnswer || '').trim();
  }
  if (!answer) return;

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    showToast('⚠ WebSocket 未连接，请刷新页面重试', false);
    return;
  }

  // Immediately lock the UI so user knows it was submitted
  const qDiv = document.querySelector(`[data-task-question-id="${taskId}"] .task-question`);
  if (qDiv) {
    const btn = qDiv.querySelector('button');
    if (btn) { btn.disabled = true; btn.textContent = '发送中…'; }
  }

  ws.send(JSON.stringify({ type: 'task_answer', task_id: taskId, answer }));
  _pendingTaskQuestions.delete(taskId);

  // Replace input with answered state
  if (qDiv) {
    const _L = I18N[currentLang] || {};
    setTimeout(() => {
      qDiv.innerHTML = `
        <div class="task-question-label">🤖 Task #${taskIdShort} — ${_L.task_question_label || '需要确认'}</div>
        <div class="task-question-answered">✅ ${_L.task_question_answered || '已回复'}: ${answer.replace(/</g,'&lt;')}</div>`;
    }, 200);
  }
}

function showToast(msg, success) {
  const t = document.createElement('div');
  t.className = 'toast';
  const dot = success === true ? '🟢' : success === false ? '🔴' : '🔵';
  t.textContent = `${dot} ${msg}`;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

function linkify(text) {
  const safe = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  // [label](url) markdown links
  const withMd = safe.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  // bare URLs not already inside href="..."
  return withMd.replace(
    /((?:^|[^"=])(https?:\/\/[^\s<,，。！？\)）]+))/g,
    (match, full, url, offset, str) => {
      const before = str.slice(0, offset + full.length - url.length);
      if (/href="$/.test(before)) return match;
      const prefix = full.slice(0, full.length - url.length);
      return `${prefix}<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
    }
  );
}

function appendMessage(role, text, category, intent, at) {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  // Detect outsource plan: extract task_id from <!-- task_id:xxx --> comment (use last match)
  const taskIdMatches = [...text.matchAll(/<!--\s*task_id:([a-f0-9\-]+)\s*-->/gi)];
  const taskId = taskIdMatches.length ? taskIdMatches[taskIdMatches.length - 1][1] : null;
  const displayText = taskId ? text.replace(/<!--[\s\S]*?-->/g, '').trimEnd() : text;

  bubble.innerHTML = linkify(displayText);

  // Append confirm/cancel buttons for outsource plan messages
  if (taskId && role === 'agent') {
    const actions = document.createElement('div');
    actions.className = 'outsource-actions';
    actions.dataset.taskId = taskId;
    div.appendChild(bubble);
    div.appendChild(actions);

    // Fetch actual task status, then render correct UI
    fetch(`http://${location.hostname}:${API_PORT}/api/outsource/tasks/${taskId}`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(task => {
        if (!task) { actions.remove(); return; }
        updateTaskActions(taskId, task.status, task.result);
      })
      .catch(() => { actions.remove(); });
  } else {
    div.appendChild(bubble);
  }

  if (role === 'agent' && (category || intent)) {
    const meta = document.createElement('div');
    meta.className = 'msg-meta';
    if (category) meta.innerHTML += `<span class="meta-tag">${category}</span>`;
    if (intent)   meta.innerHTML += `<span class="meta-tag">${intent}</span>`;
    div.appendChild(meta);
  }
  if (at) {
    const time = document.createElement('div');
    time.className = 'msg-time';
    time.textContent = new Date(at).toLocaleString();
    div.appendChild(time);
  }
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// Update task action area by task_id
function updateTaskActions(taskId, status, resultText, filesChanged, stepsCount) {
  const actions = document.querySelector(`.outsource-actions[data-task-id="${taskId}"]`);
  if (!actions) return;
  const _L = I18N[currentLang] || {};
  if (status === 'pending') {
    const btnConfirm = document.createElement('button');
    btnConfirm.className = 'outsource-btn confirm';
    btnConfirm.textContent = _L.confirm_start || '✅ 确认开始';
    btnConfirm.onclick = () => outsourceConfirm(taskId, actions);
    const btnCancel = document.createElement('button');
    btnCancel.className = 'outsource-btn cancel';
    btnCancel.textContent = _L.cancel_task || '❌ 取消';
    btnCancel.onclick = () => outsourceCancel(taskId, actions);
    actions.innerHTML = '';
    actions.appendChild(btnConfirm);
    actions.appendChild(btnCancel);
  } else if (status === 'running') {
    actions.innerHTML = `<span class="outsource-status confirmed">🚀 ${_L.task_running || '后台执行中'} · ID: ${taskId.slice(0,8)}</span>`;
    pollTaskUntilDone(taskId);
  } else if (status === 'done') {
    let summary = resultText ? `\n${resultText}` : '';
    if (stepsCount) summary += `\n\n步骤数：${stepsCount}`;
    if (filesChanged && filesChanged.length) summary += `\n\n修改文件：\n${filesChanged.map(f => '· ' + f).join('\n')}`;
    actions.innerHTML = `<span class="outsource-status confirmed" style="white-space:pre-wrap">✅ ${_L.task_done || '执行完成'}${summary}</span>`;
  } else if (status === 'planning') {
    actions.innerHTML = `<span class="outsource-status confirmed">🔄 ${_L.task_planning || '规划中…'}</span>`;
    pollTaskUntilDone(taskId);
  } else if (status === 'failed') {
    const btnRetry = document.createElement('button');
    btnRetry.className = 'outsource-btn confirm';
    btnRetry.textContent = _L.retry_task || '↺ 重试';
    btnRetry.style.cssText = 'border-color:rgba(63,185,80,0.4);color:var(--green,#3fb950);';
    btnRetry.onclick = () => outsourceRetry(taskId, actions);
    actions.innerHTML = `<span class="outsource-status cancelled">❌ ${_L.task_failed || '执行失败'}</span>`;
    actions.appendChild(btnRetry);
  } else if (status === 'suspended') {
    const btnResume = document.createElement('button');
    btnResume.className = 'outsource-btn confirm';
    btnResume.textContent = _L.resume_task || '▶ 继续执行';
    btnResume.style.cssText = 'border-color:rgba(130,80,200,0.5);color:#a78bfa;';
    btnResume.onclick = () => outsourceResume(taskId, actions);
    actions.innerHTML = `<span class="outsource-status" style="color:#a78bfa;">⏸ ${_L.task_suspended || '已挂起（并发上限）'}</span>`;
    actions.appendChild(btnResume);
  } else {
    actions.innerHTML = `<span class="outsource-status cancelled">❌ ${_L.task_cancelled || '已取消'}</span>`;
  }
}

// Poll task status every 4s when running (e.g. after page refresh)
const _activePollers = {};  // taskId -> timer, prevent duplicate polls

async function outsourceRetry(taskId, actions) {
  actions.querySelectorAll('button').forEach(b => b.disabled = true);
  const _L = I18N[currentLang] || {};
  try {
    const r = await fetch(`http://${location.hostname}:${API_PORT}/api/outsource/tasks/${taskId}/retry`, {
      method: 'POST',
      headers: authHeaders(),
    });
    const data = await r.json();
    if (data.ok) {
      updateTaskActions(taskId, 'running');
    } else {
      actions.innerHTML = `<span class="outsource-status cancelled">❌ ${data.reason || 'Retry failed'}</span>`;
      setTimeout(() => updateTaskActions(taskId, 'failed'), 2000);
    }
  } catch(e) {
    updateTaskActions(taskId, 'failed');
  }
}

async function outsourceResume(taskId, actions) {
  actions.querySelectorAll('button').forEach(b => b.disabled = true);
  const _L = I18N[currentLang] || {};
  try {
    const r = await fetch(`http://${location.hostname}:${API_PORT}/api/outsource/tasks/${taskId}/resume`, {
      method: 'POST',
      headers: authHeaders(),
    });
    const data = await r.json();
    if (data.ok) {
      updateTaskActions(taskId, 'running');
    } else {
      actions.innerHTML = `<span class="outsource-status" style="color:#a78bfa;">⏸ ${_L.task_suspended || '已挂起'} — ${data.reason || ''}</span>`;
      const btn = document.createElement('button');
      btn.className = 'outsource-btn confirm';
      btn.textContent = _L.resume_task || '▶ 继续执行';
      btn.style.cssText = 'border-color:rgba(130,80,200,0.5);color:#a78bfa;';
      btn.onclick = () => outsourceResume(taskId, actions);
      actions.appendChild(btn);
    }
  } catch(e) {
    updateTaskActions(taskId, 'suspended');
  }
}

function pollTaskUntilDone(taskId) {
  if (_activePollers[taskId]) return;  // Already polling
  let _pollErrors = 0;
  const _maxErrors = 5;
  const _maxPolls = 900;  // 60 minutes max (900 * 4s)
  let _pollCount = 0;
  const timer = setInterval(() => {
    _pollCount++;
    if (_pollCount > _maxPolls) {
      clearInterval(timer);
      delete _activePollers[taskId];
      return;
    }
    fetch(`http://${location.hostname}:${API_PORT}/api/outsource/tasks/${taskId}`, { headers: authHeaders() })
      .then(r => {
        if (!r.ok) { if (++_pollErrors >= _maxErrors) { clearInterval(timer); delete _activePollers[taskId]; } return null; }
        _pollErrors = 0;
        return r.json();
      })
      .then(task => {
        if (!task || task.status === 'running' || task.status === 'pending' || task.status === 'planning') return;
        clearInterval(timer);
        delete _activePollers[taskId];
        updateTaskActions(taskId, task.status, task.result, task.files_changed, (task.steps || []).length);
      })
      .catch(() => { if (++_pollErrors >= _maxErrors) { clearInterval(timer); delete _activePollers[taskId]; } });
  }, 4000);
  _activePollers[taskId] = timer;
}

function outsourceConfirm(taskId, actions) {
  // Disable buttons immediately to prevent double-click
  actions.querySelectorAll('button').forEach(b => b.disabled = true);
  const _L = I18N[currentLang] || {};
  actions.innerHTML = `<span class="outsource-status confirmed">${_L.task_starting || '启动中…'}</span>`;

  fetch(`http://${location.hostname}:${API_PORT}/api/outsource/tasks/${taskId}/confirm`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        updateTaskActions(taskId, 'running');
      } else {
        // Restore buttons if failed
        actions.innerHTML = `<span class="outsource-status cancelled">❌ ${data.reason || 'Failed'}</span>`;
        setTimeout(() => updateTaskActions(taskId, 'pending'), 2000);
      }
    })
    .catch(() => {
      actions.innerHTML = `<span class="outsource-status cancelled">❌ 网络错误</span>`;
      setTimeout(() => updateTaskActions(taskId, 'pending'), 2000);
    });
}

function outsourceCancel(taskId, actions) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'outsource_cancel', task_id: taskId }));
  updateTaskActions(taskId, 'failed');
}

function appendImageMessage(role, dataUrl, caption) {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  const img = document.createElement('img');
  img.src = dataUrl;
  img.className = 'msg-image';
  bubble.appendChild(img);
  if (caption) {
    const p = document.createElement('div');
    p.textContent = caption;
    bubble.appendChild(p);
  }
  div.appendChild(bubble);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function showThinking() {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg agent';
  div.id = 'thinking';
  div.innerHTML = '<div class="bubble thinking"><span></span><span></span><span></span></div>';
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}
function removeThinking() { const el = document.getElementById('thinking'); if (el) el.remove(); }

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

// ── Session ───────────────────────────────────────────────────────────
function newSession() {
  localStorage.removeItem(STORAGE_KEY); sessionId = null;
  document.getElementById('messages').innerHTML = '';
  document.getElementById('sessionIdDisplay').textContent = '—';
  if (ws) ws.close();
  closeSidebar(); connect(); loadSessionList();
}

// ── Input events ──────────────────────────────────────────────────────
document.getElementById('input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); sendMessage(); }
});
document.getElementById('input').addEventListener('input', function () {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 140) + 'px';
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
  if (saved === 'light') document.body.classList.add('light');
  updateThemeBtn();
})();

function toggleTheme() {
  const isLight = document.body.classList.toggle('light');
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
  updateThemeBtn();
}

init();

document.addEventListener('DOMContentLoaded', function() {
  var msgs = document.querySelector('.messages');
  if (msgs) {
  }
});
