// ── Constants ────────────────────────────────────────────────────────
const API_PORT = 8400;
// Per-owner localStorage namespace. The chat template injects window.__JK_OWNER_ID__
// from g.owner_id; falls back to 1 in legacy single-user mode.
const _OWNER = (window.__JK_OWNER_ID__ || 1);
const _NS = `jkriver_o${_OWNER}_`;
const STORAGE_KEY = _NS + 'session_id';
const SESSION_ACTIVE_KEY = _NS + 'session_active';  // '1' when current session has rendered ≥1 message; consulted by zero-state sync init in chat.html
const TOKEN_COOKIE = 'jkriver_token';
const AUTO_SLEEP_KEY = _NS + 'auto_sleep';
const SLEEP_MODE_KEY = _NS + 'sleep_mode';
const SLEEP_INTERVAL_KEY = _NS + 'sleep_hours';
const SLEEP_TIME_KEY = _NS + 'sleep_time';
const LANG_KEY = _NS + 'lang';
const SIDEBAR_KEY = _NS + 'sidebar_open';
const SYS_STATS_KEY = _NS + 'sys_stats';
const SYS_STATS_INTERVAL_KEY = _NS + 'sys_stats_interval';
const TOKEN_USAGE_KEY = _NS + 'token_usage';

// ── Shared mutable globals ──────────────────────────────────────────
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

function setLang(lang) {
  currentLang = lang;
  localStorage.setItem(LANG_KEY, lang);
  document.cookie = `jk_lang=${lang}; path=/; max-age=31536000; SameSite=Lax`;
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

// ── Utility functions ────────────────────────────────────────────────
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

function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

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

function fmtTokens(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return String(n);
}

function fmtSpeed(bps) {
  if (bps >= 1024 * 1024) return (bps / 1024 / 1024).toFixed(1) + 'M';
  if (bps >= 1024) return (bps / 1024).toFixed(0) + 'K';
  return bps + 'B';
}

function fmtPct(v, warnAt=70, critAt=90) {
  const cls = v >= critAt ? 'sys-stat-crit' : v >= warnAt ? 'sys-stat-warn' : '';
  return `<span class="${cls}">${v}%</span>`;
}
