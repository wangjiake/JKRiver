// ══════════════════════════════════════
// 多语言
// ══════════════════════════════════════
const I18N = {
  zh: {
    title: '个人资料', db_label: '数据库', nav_chat: '聊天', nav_profile: '个人资料', nav_system: '系统', nav_finance: '财务追踪', nav_health: '健康追踪',
    stat_sessions: '已处理会话', stat_observations: '观察记录',
    stat_confirmed: '已确认', stat_suspected: '待确认',
    stat_closed: '历史变迁', stat_disputes: '未解决矛盾',
    filter_title: '分类筛选', filter_all: '全部',
    tab_profile: '当前画像', tab_timeline: '时间线', tab_snapshot: '月度快照', tab_observations: '观察记录', tab_relationships: '人际关系',
    loading: '加载中',
    section_confirmed: '已确认画像', section_suspected: '待确认画像',
    layer_confirmed: '已确认', layer_suspected: '待确认',
    disputed: '有争议',
    mentions: '提及 {n} 次', source: '来源', confirmed_at: '确认', updated: '更新',
    current: '至今',
    empty_profile: '暂无画像数据', empty_timeline: '暂无时间线数据', empty_snapshot: '该月暂无画像数据', empty_obs: '暂无观察记录', empty_rel: '暂无人际关系数据',
    snapshot_new: '本月新增', snapshot_select: '选择月份', snapshot_all: '全部', snapshot_new_only: '本月新增',
    snapshot_facts: '条记录', snapshot_new_abbr: '条新增', snapshot_confirmed_abbr: '已确认', snapshot_suspected_abbr: '待确认',
    obs_all: '全部',
    obs_type: '类型', obs_subject: '主题', obs_context: '上下文', obs_session: '会话',
    obs_types: { statement: '陈述', behavior: '行为', preference: '偏好', fact: '事实', opinion: '观点', emotion: '情绪', goal: '目标', habit: '习惯', background: '背景', relationship: '关系', other: '其他' },
    first_seen: '首次', last_seen: '最近', unknown: '未知',
    month_names: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
    review_reject: '标记为错误信息', review_unreject: '取消标记', review_close: '人工关闭', review_reopen: '取消关闭',
    review_rejected: '已标记错误', review_human_closed: '人工关闭',
    review_note_placeholder: '备注（可选）', review_end_time: '结束时间', review_confirm: '确定', review_cancel: '取消',
    review_close_title: '人工关闭', review_success: '操作成功',
    err_generic: '操作失败', err_request_failed: '请求失败：',
    filter_active: '全部', filter_human_closed: '人工关闭', filter_rejected: '标记为错误',
  },
  en: {
    title: 'User Profile', db_label: 'Database', nav_chat: 'Chat', nav_profile: 'Profile', nav_system: 'System', nav_finance: 'Finance', nav_health: 'Health',
    stat_sessions: 'Sessions', stat_observations: 'Observations',
    stat_confirmed: 'Confirmed', stat_suspected: 'Suspected',
    stat_closed: 'History', stat_disputes: 'Disputes',
    filter_title: 'Filter', filter_all: 'All',
    tab_profile: 'Profile', tab_timeline: 'Timeline', tab_snapshot: 'Snapshots', tab_observations: 'Observations', tab_relationships: 'Relationships',
    loading: 'Loading',
    section_confirmed: 'Confirmed', section_suspected: 'Suspected',
    layer_confirmed: 'Confirmed', layer_suspected: 'Suspected',
    disputed: 'Disputed',
    mentions: '{n} mentions', source: 'Source', confirmed_at: 'Confirmed', updated: 'Updated',
    current: 'Present',
    empty_profile: 'No profile data', empty_timeline: 'No timeline data', empty_snapshot: 'No profile data for this month', empty_obs: 'No observations', empty_rel: 'No relationship data',
    snapshot_new: 'New this month', snapshot_select: 'Select month', snapshot_all: 'All', snapshot_new_only: 'New this month',
    snapshot_facts: 'facts', snapshot_new_abbr: 'new', snapshot_confirmed_abbr: 'confirmed', snapshot_suspected_abbr: 'suspected',
    obs_all: 'All',
    obs_type: 'Type', obs_subject: 'Subject', obs_context: 'Context', obs_session: 'Session',
    obs_types: { statement: 'Statement', behavior: 'Behavior', preference: 'Preference', fact: 'Fact', opinion: 'Opinion', emotion: 'Emotion', goal: 'Goal', habit: 'Habit', background: 'Background', relationship: 'Relationship', other: 'Other' },
    first_seen: 'First', last_seen: 'Last', unknown: 'Unknown',
    month_names: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
    review_reject: 'Mark as Error', review_unreject: 'Unmark', review_close: 'Manual Close', review_reopen: 'Cancel Close',
    review_rejected: 'Marked Wrong', review_human_closed: 'Manually Closed',
    review_note_placeholder: 'Note (optional)', review_end_time: 'End Time', review_confirm: 'Confirm', review_cancel: 'Cancel',
    review_close_title: 'Manual Close', review_success: 'Success',
    err_generic: 'Error', err_request_failed: 'Request failed: ',
    filter_active: 'All', filter_human_closed: 'Manually Closed', filter_rejected: 'Marked as Error',
  },
  ja: {
    title: 'ユーザープロフィール', db_label: 'データベース', nav_chat: 'チャット', nav_profile: 'プロフィール', nav_system: 'システム', nav_finance: '家計簿', nav_health: '健康',
    stat_sessions: '処理済み会話', stat_observations: '観察記録',
    stat_confirmed: '確認済み', stat_suspected: '未確認',
    stat_closed: '変遷履歴', stat_disputes: '未解決矛盾',
    filter_title: 'カテゴリ', filter_all: 'すべて',
    tab_profile: '現在のプロフィール', tab_timeline: 'タイムライン', tab_snapshot: '月別スナップショット', tab_observations: '観察記録', tab_relationships: '人間関係',
    loading: '読み込み中',
    section_confirmed: '確認済みプロフィール', section_suspected: '未確認プロフィール',
    layer_confirmed: '確認済み', layer_suspected: '未確認',
    disputed: '異議あり',
    mentions: '{n} 回言及', source: '情報源', confirmed_at: '確認日', updated: '更新日',
    current: '現在',
    empty_profile: 'プロフィールデータなし', empty_timeline: 'タイムラインデータなし', empty_snapshot: 'この月のデータなし', empty_obs: '観察記録なし', empty_rel: '人間関係データなし',
    snapshot_new: '今月新規', snapshot_select: '月を選択', snapshot_all: 'すべて', snapshot_new_only: '今月新規',
    snapshot_facts: '件の記録', snapshot_new_abbr: '件の新規', snapshot_confirmed_abbr: '確認済み', snapshot_suspected_abbr: '未確認',
    obs_all: 'すべて',
    obs_type: 'タイプ', obs_subject: '主題', obs_context: 'コンテキスト', obs_session: 'セッション',
    obs_types: { statement: '発言', behavior: '行動', preference: '好み', fact: '事実', opinion: '意見', emotion: '感情', goal: '目標', habit: '習慣', background: '背景', relationship: '関係', other: 'その他' },
    first_seen: '初回', last_seen: '最近', unknown: '不明',
    month_names: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
    review_reject: 'エラー標記', review_unreject: '標記解除', review_close: '手動閉鎖', review_reopen: '閉鎖取消',
    review_rejected: 'エラー標記済み', review_human_closed: '手動閉鎖済み',
    review_note_placeholder: '備考（任意）', review_end_time: '終了時間', review_confirm: '確定', review_cancel: 'キャンセル',
    review_close_title: '手動閉鎖', review_success: '操作成功',
    err_generic: 'エラー', err_request_failed: 'リクエスト失敗: ',
    filter_active: 'すべて', filter_human_closed: '手動閉鎖', filter_rejected: 'エラー標記',
  }
};

const LANG_KEY = 'jkriver_lang';

function detectLang() {
  const saved = localStorage.getItem(LANG_KEY);
  if (saved && I18N[saved]) return saved;
  const lang = (navigator.language || navigator.userLanguage || 'en').toLowerCase();
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

function monthName(m) {
  const names = (I18N[currentLang] || I18N.en).month_names;
  return names[m - 1] || m;
}

function tObsType(type) {
  const map = (I18N[currentLang] || I18N.en).obs_types || {};
  return map[type] || type;
}

function setLang(lang) {
  currentLang = lang;
  localStorage.setItem(LANG_KEY, lang);
  document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.textContent.trim() === {zh:'中文',en:'EN',ja:'日本語'}[lang]));
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (I18N[lang][key]) el.textContent = I18N[lang][key];
  });
  renderCurrent();
}

// ══════════════════════════════════════
// 数据
// ══════════════════════════════════════
let allProfile = [];
let allTimeline = [];
let allObservations = [];
let allRelationships = [];
let snapshotMonths = [];
let snapshotData = [];
let currentSnapshotMonth = '';
let snapshotFilter = 'all'; // 'all' or 'new'
let obsMonthFilter = ''; // '' = all, 'YYYY-MM' = specific month
let currentCategory = '';
let currentTab = 'profile';
let profileStatusFilter = 'active'; // 'active' | 'human_closed' | 'rejected'

function renderStats(stats) {
  document.getElementById('s-sessions').textContent = stats.sessions;
  document.getElementById('s-observations').textContent = stats.observations;
  document.getElementById('s-confirmed').textContent = stats.confirmed;
  document.getElementById('s-suspected').textContent = stats.suspected;
  document.getElementById('s-closed').textContent = stats.closed;
  document.getElementById('s-disputes').textContent = stats.disputes;
}

async function init() {
  setLang(currentLang);
  const [stats, profile, timeline, observations, relationships, months] = await Promise.all([
    fetch('/api/stats').then(r => r.json()),
    fetch('/api/profile').then(r => r.json()),
    fetch('/api/timeline').then(r => r.json()),
    fetch('/api/observations').then(r => r.json()),
    fetch('/api/relationships').then(r => r.json()),
    fetch('/api/snapshot/months').then(r => r.json()),
  ]);
  snapshotMonths = months;

  renderStats(stats);

  allProfile = profile;
  allTimeline = timeline;
  allObservations = observations;
  allRelationships = relationships;

  document.getElementById('t-profile').textContent = profile.length;
  document.getElementById('t-timeline').textContent = timeline.length;
  document.getElementById('t-obs').textContent = observations.length;
  document.getElementById('t-rel').textContent = relationships.length;

  updateSidebar();
  renderCurrent();
}

function filterCategory(btn) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentCategory = btn.dataset.category;
  renderCurrent();
}

function switchTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  tab.classList.add('active');
  currentTab = tab.dataset.tab;
  currentCategory = '';
  obsMonthFilter = '';
  snapshotFilter = 'all';
  updateSidebar();
  renderCurrent();
}

function updateSidebar() {
  const catList = document.getElementById('category-list');
  catList.innerHTML = '';
  // 重置"全部"按钮
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('.filter-btn[data-category=""]').classList.add('active');

  if (currentTab === 'snapshot') {
    // 快照：按 category 筛选（从快照数据中）
    if (snapshotData.length > 0) {
      const categories = [...new Set(snapshotData.map(p => p.category))].sort();
      categories.forEach(cat => {
        const count = snapshotData.filter(p => p.category === cat).length;
        const btn = document.createElement('button');
        btn.className = 'filter-btn';
        btn.dataset.category = cat;
        btn.textContent = `${cat} (${count})`;
        btn.onclick = function() { filterCategory(this); };
        catList.appendChild(btn);
      });
    }
  } else if (currentTab === 'observations') {
    // 观察记录：按 observation_type 筛选
    const types = [...new Set(allObservations.map(o => o.observation_type || 'other'))].sort();
    types.forEach(type => {
      const count = allObservations.filter(o => (o.observation_type || 'other') === type).length;
      const btn = document.createElement('button');
      btn.className = 'filter-btn';
      btn.dataset.category = type;
      btn.textContent = `${type} (${count})`;
      btn.onclick = function() { filterCategory(this); };
      catList.appendChild(btn);
    });
  } else if (currentTab === 'relationships') {
    // 人际关系：按 relation 筛选
    const relations = [...new Set(allRelationships.map(r => r.relation || 'other'))].sort();
    relations.forEach(rel => {
      const count = allRelationships.filter(r => (r.relation || 'other') === rel).length;
      const btn = document.createElement('button');
      btn.className = 'filter-btn';
      btn.dataset.category = rel;
      btn.textContent = `${rel} (${count})`;
      btn.onclick = function() { filterCategory(this); };
      catList.appendChild(btn);
    });
  } else {
    // 根据 tab 选择数据源
    const source = currentTab === 'timeline' ? allTimeline : allProfile;
    const categories = [...new Set(source.map(p => p.category))].sort();
    categories.forEach(cat => {
      const count = source.filter(p => p.category === cat).length;
      const btn = document.createElement('button');
      btn.className = 'filter-btn';
      btn.dataset.category = cat;
      btn.textContent = `${cat} (${count})`;
      btn.onclick = function() { filterCategory(this); };
      catList.appendChild(btn);
    });
  }
}

function renderCurrent() {
  if (currentTab === 'profile') renderProfile();
  else if (currentTab === 'timeline') renderTimeline();
  else if (currentTab === 'snapshot') renderSnapshot();
  else if (currentTab === 'observations') renderObservations();
  else if (currentTab === 'relationships') renderRelationships();
}

// ── 画像卡片 ──
function buildProfileStatusFilter() {
  const counts = {
    active: allProfile.filter(d => !d.rejected && !d.human_end_time).length,
    human_closed: allProfile.filter(d => !d.rejected && d.human_end_time).length,
    rejected: allProfile.filter(d => d.rejected).length,
  };
  return `<div class="sub-filter" style="margin-bottom:16px">
    <button class="sub-filter-btn ${profileStatusFilter==='active'?'active':''}" onclick="setProfileStatus('active')">${t('filter_active')} <span class="count">${counts.active}</span></button>
    <button class="sub-filter-btn ${profileStatusFilter==='human_closed'?'active':''}" onclick="setProfileStatus('human_closed')">${t('filter_human_closed')} <span class="count">${counts.human_closed}</span></button>
    <button class="sub-filter-btn ${profileStatusFilter==='rejected'?'active':''}" onclick="setProfileStatus('rejected')">${t('filter_rejected')} <span class="count">${counts.rejected}</span></button>
  </div>`;
}

function setProfileStatus(s) {
  profileStatusFilter = s;
  renderProfile();
}

function renderProfile() {
  let data = allProfile;

  // 按状态筛选（三种互斥）
  if (profileStatusFilter === 'active') {
    data = data.filter(d => !d.rejected && !d.human_end_time);
  } else if (profileStatusFilter === 'human_closed') {
    data = data.filter(d => !d.rejected && d.human_end_time);
  } else if (profileStatusFilter === 'rejected') {
    data = data.filter(d => d.rejected);
  }

  if (currentCategory) data = data.filter(d => d.category === currentCategory);

  const filterHtml = buildProfileStatusFilter();

  if (data.length === 0) {
    document.getElementById('content').innerHTML = filterHtml + `<div class="empty">${t('empty_profile')}</div>`;
    return;
  }

  const confirmed = data.filter(d => d.layer === 'confirmed');
  const suspected = data.filter(d => d.layer === 'suspected');

  let html = filterHtml;
  if (confirmed.length > 0) {
    html += `<div class="section-title">${t('section_confirmed')}</div><div class="cards">`;
    confirmed.forEach(d => { html += cardHTML(d); });
    html += '</div>';
  }
  if (suspected.length > 0) {
    html += `<div class="section-title" style="margin-top:24px">${t('section_suspected')}</div><div class="cards">`;
    suspected.forEach(d => { html += cardHTML(d); });
    html += '</div>';
  }
  document.getElementById('content').innerHTML = html;
}

function cardHTML(d) {
  const disputed = d.superseded_by ? ' disputed' : '';
  const rejectedCls = d.rejected ? ' rejected' : '';
  const disputeTag = d.superseded_by ? ` <span style="color:var(--red);font-size:11px">[${t('disputed')}]</span>` : '';
  const rejectedTag = d.rejected ? `<span class="rejected-badge">${t('review_rejected')}</span>` : '';
  const humanEndTag = d.human_end_time ? `<span class="human-end-badge">${t('review_human_closed')}: ${formatDate(d.human_end_time)}</span>` : '';
  const layerText = d.layer === 'confirmed' ? t('layer_confirmed') : t('layer_suspected');
  const confirmedAt = d.confirmed_at ? `<span>${t('confirmed_at')}: ${formatDate(d.confirmed_at)}</span>` : '';
  const noteHtml = d.note ? `<div class="note-text">${d.note}</div>` : '';

  // 审核按钮（三种互斥状态：正常 / 已标记错误 / 已人工关闭）
  let reviewBtns = '<div class="review-actions">';
  if (d.rejected) {
    // 已标记错误 → 只能取消标记
    reviewBtns += `<button class="review-btn ok" onclick="reviewProfile(${d.id},'unreject')">${t('review_unreject')}</button>`;
  } else if (d.human_end_time) {
    // 已人工关闭 → 只能取消关闭
    reviewBtns += `<button class="review-btn ok" onclick="reviewProfile(${d.id},'reopen')">${t('review_reopen')}</button>`;
  } else {
    // 正常状态 → 可以标记错误 或 人工关闭
    reviewBtns += `<button class="review-btn danger" onclick="reviewProfile(${d.id},'reject')">${t('review_reject')}</button>`;
    reviewBtns += `<button class="review-btn warn" onclick="showCloseModal(${d.id})">${t('review_close')}</button>`;
  }
  reviewBtns += '</div>';

  return `<div class="card ${d.layer}${disputed}${rejectedCls}">
    <div class="card-header">
      <span class="card-category">${d.category}</span>
      <span class="card-layer ${d.layer}">${layerText}${rejectedTag}${humanEndTag}</span>
    </div>
    <div class="card-subject">${d.subject}${disputeTag}</div>
    <div class="card-value">${d.value}</div>
    <div class="card-meta">
      <span>${t('mentions', {n: d.mention_count})}</span>
      <span>${t('source')}: ${d.source_type || '?'}</span>
      ${confirmedAt}
      <span>${t('updated')}: ${formatDate(d.updated_at)}</span>
    </div>
    ${noteHtml}
    ${reviewBtns}
  </div>`;
}

// ── 时间线 ──
function renderTimeline() {
  let data = allTimeline;
  if (currentCategory) data = data.filter(d => d.category === currentCategory);

  if (data.length === 0) {
    document.getElementById('content').innerHTML = `<div class="empty">${t('empty_timeline')}</div>`;
    return;
  }

  const groups = {};
  data.forEach(d => {
    const key = `${d.category}|${d.subject}`;
    if (!groups[key]) groups[key] = { category: d.category, subject: d.subject, items: [] };
    groups[key].items.push(d);
  });

  const sorted = Object.values(groups).sort((a, b) => b.items.length - a.items.length);

  let html = '<div class="timeline-container">';
  sorted.forEach(group => {
    const catClass = getCatClass(group.category);
    html += `<div class="timeline-group">`;
    html += `<div class="timeline-group-title ${catClass}">${group.category} / ${group.subject}</div>`;
    html += `<div class="timeline-track">`;
    group.items.forEach(item => {
      const isCurrent = item.end_time === null;
      const cls = isCurrent ? ' current' : '';
      const start = formatDate(item.start_time);
      const end = isCurrent ? t('current') : formatDate(item.end_time);
      const layerText = item.layer === 'confirmed' ? t('layer_confirmed') : t('layer_suspected');
      html += `<div class="timeline-item${cls}">
        <div class="timeline-value">${item.value}</div>
        <div class="timeline-dates">${start} ~ ${end}  (${layerText}, ${t('mentions', {n: item.mention_count})})</div>
      </div>`;
    });
    html += '</div></div>';
  });
  html += '</div>';
  document.getElementById('content').innerHTML = html;
}

function getCatClass(category) {
  if (['位置', '居住城市', '居住地', '出生地'].includes(category)) return 'cat-location';
  if (['职业', '工作', '职位', '教育背景'].includes(category)) return 'cat-career';
  if (['情感', '感情', '人际关系', '社交'].includes(category)) return 'cat-emotion';
  if (['兴趣爱好', '活动', '运动', '娱乐', '兴趣'].includes(category)) return 'cat-hobby';
  return 'cat-other';
}

// ── 月度快照 ──
let snapshotYearFilter = '';

function buildSnapshotHeader() {
  // 提取所有年份
  const years = [...new Set(snapshotMonths.map(m => m.substring(0, 4)))].sort();

  // 第一排：年份按钮
  let yearBtns = '';
  years.forEach(y => {
    yearBtns += `<button class="sub-filter-btn ${snapshotYearFilter===y?'active':''}" onclick="setSnapshotYear('${y}')">${y}</button>`;
  });

  // 第二排：月份 1-12（选了年份后显示）
  let monthBtns = '';
  if (snapshotYearFilter) {
    const availableMonths = new Set(
      snapshotMonths
        .filter(m => m.startsWith(snapshotYearFilter))
        .map(m => m.substring(5, 7))
    );
    monthBtns = `<div class="sub-filter" style="margin-top:8px">`;
    for (let m = 1; m <= 12; m++) {
      const mm = String(m).padStart(2, '0');
      const key = `${snapshotYearFilter}-${mm}`;
      const has = availableMonths.has(mm);
      if (has) {
        monthBtns += `<button class="sub-filter-btn ${currentSnapshotMonth===key?'active':''}" onclick="loadSnapshot('${key}')">${monthName(m)}</button>`;
      } else {
        monthBtns += `<button class="sub-filter-btn" disabled style="opacity:0.3;cursor:default">${monthName(m)}</button>`;
      }
    }
    monthBtns += `</div>`;
  }

  // 第三排：全部 / 本月新增
  let filterBtns = '';
  if (currentSnapshotMonth) {
    filterBtns = `<div class="sub-filter" style="margin-top:8px">
      <button class="sub-filter-btn ${snapshotFilter==='all'?'active':''}" onclick="setSnapshotFilter('all')">${t('snapshot_all')}</button>
      <button class="sub-filter-btn ${snapshotFilter==='new'?'active':''}" onclick="setSnapshotFilter('new')">${t('snapshot_new_only')}</button>
    </div>`;
  }

  return `<div class="snapshot-header" style="flex-direction:column;align-items:flex-start"><div class="sub-filter">${yearBtns}</div>${monthBtns}${filterBtns}</div>`;
}

function setSnapshotYear(y) {
  snapshotYearFilter = y;
  // 自动选中该年第一个有数据的月份
  const firstMonth = snapshotMonths.find(m => m.startsWith(y));
  if (firstMonth && firstMonth !== currentSnapshotMonth) {
    currentSnapshotMonth = firstMonth;
    snapshotFilter = 'all';
    snapshotData = [];
  }
  renderSnapshot();
}

function setSnapshotFilter(f) {
  snapshotFilter = f;
  renderSnapshot();
}

async function renderSnapshot() {
  // 自动初始化年份和月份
  if (!snapshotYearFilter && snapshotMonths.length > 0) {
    const lastMonth = snapshotMonths[snapshotMonths.length - 1];
    snapshotYearFilter = lastMonth.substring(0, 4);
    currentSnapshotMonth = lastMonth;
  }

  const headerHtml = buildSnapshotHeader();

  if (!currentSnapshotMonth) {
    document.getElementById('content').innerHTML = headerHtml + `<div class="empty">${t('empty_snapshot')}</div>`;
    return;
  }

  // 如果还没加载过该月数据，请求 API
  if (snapshotData.length === 0 || snapshotData._month !== currentSnapshotMonth) {
    const data = await fetch(`/api/snapshot?month=${currentSnapshotMonth}`).then(r => r.json());
    snapshotData = data;
    snapshotData._month = currentSnapshotMonth;
    updateSidebar();
  }

  let data = snapshotData;
  if (snapshotFilter === 'new') data = data.filter(d => d.is_new);
  if (currentCategory) data = data.filter(d => d.category === currentCategory);

  if (data.length === 0) {
    document.getElementById('content').innerHTML = buildSnapshotHeader() + `<div class="empty">${t('empty_snapshot')}</div>`;
    return;
  }

  const confirmed = data.filter(d => d.layer === 'confirmed');
  const suspected = data.filter(d => d.layer === 'suspected');
  const newCount = data.filter(d => d.is_new).length;

  let html = buildSnapshotHeader();
  const factLabel = snapshotFilter === 'new' ? t('snapshot_new_abbr') : t('snapshot_facts');
  const summaryParts = `${confirmed.length} ${t('snapshot_confirmed_abbr')}, ${suspected.length} ${t('snapshot_suspected_abbr')}${snapshotFilter === 'all' ? ', ' + newCount + ' ' + t('snapshot_new_abbr') : ''}`;
  html += `<div style="font-size:13px;color:var(--text-muted);margin-bottom:16px">${currentSnapshotMonth}: ${data.length} ${factLabel} (${summaryParts})</div>`;

  if (confirmed.length > 0) {
    html += `<div class="section-title">${t('section_confirmed')}</div><div class="cards">`;
    confirmed.forEach(d => { html += snapshotCardHTML(d); });
    html += '</div>';
  }
  if (suspected.length > 0) {
    html += `<div class="section-title" style="margin-top:24px">${t('section_suspected')}</div><div class="cards">`;
    suspected.forEach(d => { html += snapshotCardHTML(d); });
    html += '</div>';
  }
  document.getElementById('content').innerHTML = html;
}

async function loadSnapshot(month) {
  currentSnapshotMonth = month;
  currentCategory = '';
  snapshotFilter = 'all';
  snapshotData = [];
  await renderSnapshot();
}

function snapshotCardHTML(d) {
  const layerText = d.layer === 'confirmed' ? t('layer_confirmed') : t('layer_suspected');
  const newBadge = d.is_new ? `<span class="new-badge">${t('snapshot_new')}</span>` : '';
  const cardClass = d.is_new ? 'card new-this-month' : `card ${d.layer}`;
  return `<div class="${cardClass}">
    <div class="card-header">
      <span class="card-category">${d.category}</span>
      <span class="card-layer ${d.layer}">${layerText}${newBadge}</span>
    </div>
    <div class="card-subject">${d.subject}</div>
    <div class="card-value">${d.value}</div>
    <div class="card-meta">
      <span>${t('mentions', {n: d.mention_count})}</span>
      <span>${formatDate(d.start_time)} ~</span>
    </div>
  </div>`;
}

// ── 观察记录 ──
let obsYearFilter = ''; // '' = all, '2023' = specific year

function buildObsHeader() {
  // 提取所有年份
  const years = [...new Set(allObservations.map(o => (o.created_at || '').substring(0, 4)).filter(y => y))].sort();

  // 第一排：全部 + 年份
  let yearBtns = `<button class="sub-filter-btn ${obsYearFilter===''?'active':''}" onclick="setObsYear('')">${t('obs_all')}</button>`;
  years.forEach(y => {
    yearBtns += `<button class="sub-filter-btn ${obsYearFilter===y?'active':''}" onclick="setObsYear('${y}')">${y}</button>`;
  });

  // 第二排：月份 1-12（仅当选了年份时显示）
  let monthBtns = '';
  if (obsYearFilter) {
    const availableMonths = new Set(
      allObservations
        .filter(o => (o.created_at || '').startsWith(obsYearFilter))
        .map(o => (o.created_at || '').substring(5, 7))
    );
    monthBtns = `<div class="sub-filter" style="margin-top:8px">`;
    monthBtns += `<button class="sub-filter-btn ${obsMonthFilter===''?'active':''}" onclick="setObsMonth('')">${t('obs_all')}</button>`;
    for (let m = 1; m <= 12; m++) {
      const mm = String(m).padStart(2, '0');
      const key = `${obsYearFilter}-${mm}`;
      const has = availableMonths.has(mm);
      if (has) {
        monthBtns += `<button class="sub-filter-btn ${obsMonthFilter===key?'active':''}" onclick="setObsMonth('${key}')">${monthName(m)}</button>`;
      } else {
        monthBtns += `<button class="sub-filter-btn" disabled style="opacity:0.3;cursor:default">${monthName(m)}</button>`;
      }
    }
    monthBtns += `</div>`;
  }

  return `<div class="snapshot-header" style="flex-direction:column;align-items:flex-start"><div class="sub-filter">${yearBtns}</div>${monthBtns}</div>`;
}

function setObsYear(y) {
  obsYearFilter = y;
  obsMonthFilter = '';
  renderObservations();
}

function setObsMonth(m) {
  obsMonthFilter = m;
  renderObservations();
}

function renderObservations() {
  let data = allObservations;
  if (obsMonthFilter) {
    data = data.filter(o => (o.created_at || '').startsWith(obsMonthFilter));
  } else if (obsYearFilter) {
    data = data.filter(o => (o.created_at || '').startsWith(obsYearFilter));
  }
  if (currentCategory) data = data.filter(o => (o.observation_type || 'other') === currentCategory);

  const headerHtml = buildObsHeader();

  if (data.length === 0) {
    document.getElementById('content').innerHTML = headerHtml + `<div class="empty">${t('empty_obs')}</div>`;
    return;
  }

  // 按 observation_type 分组
  const groups = {};
  data.forEach(o => {
    const type = o.observation_type || 'other';
    if (!groups[type]) groups[type] = [];
    groups[type].push(o);
  });

  const sortedTypes = Object.keys(groups).sort((a, b) => groups[b].length - groups[a].length);

  let html = headerHtml;
  sortedTypes.forEach(type => {
    const items = groups[type];
    html += `<div class="section-title" style="margin-top:16px">${tObsType(type)} <span style="font-size:12px;color:var(--text-faint)">(${items.length})</span></div>`;
    html += '<div class="cards">';
    items.forEach(o => {
      const subjectTag = o.subject ? `<span class="obs-subject-tag">${o.subject}</span>` : '';
      const cls = o.classification || '';
      const clsTag = cls ? `<span class="obs-cls-tag ${cls}">${cls}</span>` : '';
      const contextLine = o.context ? `<div class="obs-context">${o.context}</div>` : '';
      const rejectedCls = o.rejected ? ' rejected' : '';
      const rejectedTag = o.rejected ? `<span class="rejected-badge">${t('review_rejected')}</span>` : '';
      const noteHtml = o.note ? `<div class="note-text">${o.note}</div>` : '';
      let obsBtns = '<div class="review-actions">';
      if (o.rejected) {
        obsBtns += `<button class="review-btn ok" onclick="reviewObs(${o.id},'unreject')">${t('review_unreject')}</button>`;
      } else {
        obsBtns += `<button class="review-btn danger" onclick="reviewObs(${o.id},'reject')">${t('review_reject')}</button>`;
      }
      obsBtns += '</div>';
      html += `<div class="obs-card${rejectedCls}">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <div style="display:flex;gap:6px;align-items:center">${subjectTag}${clsTag}${rejectedTag}</div>
          <span style="font-size:11px;color:var(--text-faint)">${formatDate(o.created_at)}</span>
        </div>
        <div class="obs-content">${o.content}</div>
        ${contextLine}
        ${noteHtml}
        ${obsBtns}
      </div>`;
    });
    html += '</div>';
  });
  document.getElementById('content').innerHTML = html;
}

// ── 人际关系 ──
function renderRelationships() {
  let data = allRelationships;
  if (currentCategory) data = data.filter(r => (r.relation || 'other') === currentCategory);

  if (data.length === 0) {
    document.getElementById('content').innerHTML = `<div class="empty">${t('empty_rel')}</div>`;
    return;
  }
  let html = '<div class="cards">';
  data.forEach(r => {
    let details = '';
    if (r.details && typeof r.details === 'object') {
      details = Object.entries(r.details).map(([k,v]) => `${k}: ${v}`).join(', ');
    } else if (r.details && typeof r.details === 'string') {
      try { const d = JSON.parse(r.details); details = Object.entries(d).map(([k,v]) => `${k}: ${v}`).join(', '); } catch(e) { details = r.details; }
    }
    html += `<div class="rel-card">
      <div class="rel-name">${r.name || t('unknown')}</div>
      <div class="rel-relation">${r.relation}</div>
      ${details ? `<div class="rel-details">${details}</div>` : ''}
      <div class="card-meta" style="margin-top:8px">
        <span>${t('mentions', {n: r.mention_count})}</span>
        <span>${t('first_seen')}: ${formatDate(r.first_mentioned_at)}</span>
        <span>${t('last_seen')}: ${formatDate(r.last_mentioned_at)}</span>
      </div>
    </div>`;
  });
  html += '</div>';
  document.getElementById('content').innerHTML = html;
}

function formatDate(s) {
  if (!s) return '?';
  return s.substring(0, 10);
}

// ── 人工审核 ──

async function reviewProfile(id, action, extra) {
  const body = { id, action, ...extra };
  if (action === 'reject' || action === 'unreject' || action === 'reopen') {
    if (!body.note && body.note !== '') {
      const note = prompt(t('review_note_placeholder'), '');
      if (note === null) return; // 取消
      body.note = note;
    }
  }
  try {
    const res = await fetch('/api/review/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.ok) {
      // 重新加载数据
      await reloadCurrentTab();
    } else {
      alert(data.error || t('err_generic'));
    }
  } catch (e) {
    alert(t('err_request_failed') + e.message);
  }
}

async function reviewObs(id, action) {
  const body = { id, action };
  if (action === 'reject' || action === 'unreject') {
    const note = prompt(t('review_note_placeholder'), '');
    if (note === null) return;
    body.note = note;
  }
  try {
    const res = await fetch('/api/review/observation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.ok) {
      await reloadCurrentTab();
    } else {
      alert(data.error || t('err_generic'));
    }
  } catch (e) {
    alert(t('err_request_failed') + e.message);
  }
}

function showCloseModal(factId) {
  const now = new Date().toISOString().substring(0, 16);
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `<div class="modal-box">
    <h3>${t('review_close_title')}</h3>
    <label>${t('review_end_time')}</label>
    <input type="datetime-local" id="modal-end-time" value="${now}">
    <label>${t('review_note_placeholder')}</label>
    <textarea id="modal-note"></textarea>
    <div class="modal-btns">
      <button class="btn-cancel" onclick="this.closest('.modal-overlay').remove()">${t('review_cancel')}</button>
      <button class="btn-confirm" onclick="submitClose(${factId})">${t('review_confirm')}</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
}

async function submitClose(factId) {
  const endTime = document.getElementById('modal-end-time').value;
  const note = document.getElementById('modal-note').value;
  document.querySelector('.modal-overlay').remove();
  await reviewProfile(factId, 'close', {
    human_end_time: endTime ? new Date(endTime).toISOString() : null,
    note: note || '',
  });
}

async function reloadCurrentTab() {
  if (currentTab === 'profile') {
    allProfile = await fetch('/api/profile').then(r => r.json());
    renderProfile();
  } else if (currentTab === 'timeline') {
    allTimeline = await fetch('/api/timeline').then(r => r.json());
    renderTimeline();
  } else if (currentTab === 'snapshot') {
    snapshotData = [];
    await renderSnapshot();
  } else if (currentTab === 'observations') {
    allObservations = await fetch('/api/observations').then(r => r.json());
    renderObservations();
  }
  // 刷新统计
  const stats = await fetch('/api/stats').then(r => r.json());
  renderStats(stats);
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

init();
