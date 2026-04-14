const API_PORT = 8400;
const LANG_KEY = 'jkriver_lang';

const I18N = {
  zh: {
    nav_chat: '聊天', nav_profile: '个人资料', nav_system: '系统',
    loading: '加载中...', load_error: '无法加载系统信息：',
    section_overview: '系统概览',
    section_tools: '内置工具',
    section_agents: '智能体',
    section_skills: '技能',
    section_mcp: 'MCP 服务',
    empty_tools: '无内置工具', empty_agents: '无已配置 Agent', empty_skills: '暂无技能', show_more: '展开', show_less: '收起',
    install_skill: '安装技能', install_skill_tip: '安装技能', install_skill_title: '安装技能',
    install_skill_desc: '粘贴 YAML 或 SKILL.md 格式内容，安装后立即生效。',
    install_skill_placeholder: '粘贴技能 YAML 或 SKILL.md…', badge_file: '已安装', badge_skillhub: 'SkillHub',
    tab_paste: '粘贴安装', tab_hub: 'SkillHub 搜索',
    hub_desc: '输入技能名称从 SkillHub 搜索安装（如 explain-code）。',
    hub_search_btn: '获取', hub_searching: '搜索中…', hub_not_found: '未找到该技能，请尝试直接粘贴 SKILL.md 内容。',
    empty_mcp: '无 MCP 服务',
    label_language: '语言', label_llm_provider: 'LLM 提供商',
    label_llm_model: 'LLM 模型', label_llm_api: 'LLM API',
    label_llm_key: 'LLM 密钥', label_telegram_token: 'Telegram Token',
    label_discord_token: 'Discord Token',
    label_embedding: '语义搜索', label_embedding_model: '向量模型', label_cloud_llm: '云兜底模型',
    label_public_mode: '公网访问', label_proactive: '主动推送',
    label_tts: '语音合成', label_telegram: 'Telegram Bot',
    label_discord: 'Discord Bot', label_mcp: 'MCP',
    label_params: '参数', label_keywords: '关键词',
    label_schedule: '定时', label_command: '命令',
    no_key: '未配置密钥',
    edit_confirm: '确认', edit_cancel: '取消',
    edit_placeholder: '输入新值', edit_placeholder_sensitive: '输入新密钥（留空则不修改）',
    not_set: '未配置',
    badge_builtin: '内置', badge_agent: '智能体', badge_skill: '技能', badge_mcp: 'MCP',
    on: '开', off: '关', toggle_theme: '切换主题', toggle_click: '点击切换',
    restart_timeout: '重启超时，请手动刷新页面。', err_failed: '操作失败：',
    banner_msg: '配置已修改，需要重启服务后生效', btn_restart: '立即重启', btn_revert: '撤销修改', btn_cancel: '取消', btn_install: '安装',
    restarting: '正在重启...', reverting: '正在撤销...',
    label_temperature: '温度', label_max_tokens: '最大Token', label_temp_dir: '临时目录',
    label_allowed_ids: '允许的用户ID', label_voice_zh: '中文语音', label_voice_en: '英文语音',
    label_max_chars: '最大字符数', label_api_base: 'API 地址',
    label_interval: '推送间隔(分钟)', label_quiet_start: '免打扰开始', label_quiet_end: '免打扰结束',
    label_max_per_day: '每日最大条数', label_min_gap: '最小间隔(分钟)', label_access_token: '访问令牌',
    label_bot_token: 'Bot Token',
    section_llm: 'LLM 主模型', section_telegram: 'Telegram Bot', section_discord: 'Discord Bot',
    section_tts_config: '语音合成配置', section_embedding_config: '语义搜索配置',
    section_proactive_config: '主动推送配置', section_public_config: '公网访问配置',
    hint_allowed_ids: '留空=所有人，多个ID用逗号分隔',
    confirm_delete: '确定要删除「{name}」吗？此操作不可撤销。',
    delete_tip: '删除',
    add_provider: '添加提供商', label_new_name: '名称', label_new_model: '模型', label_new_base: 'API 地址',
    label_priority: '优先级', label_search: '网页搜索',
    label_escalation_auto: '自动备用', label_escalation_feedback: '启用备用时通知用户',
    label_escalation_min_length: '最短回复字数',
    section_cloud_providers: '提供商配置', section_cloud_escalation: '备用策略',
    provider_no_key: '未填写密钥',
    label_timezone: '时区',
    section_database: '数据库', label_db_name: '数据库名', label_db_user: '用户名', label_db_host: '主机',
    section_session_memory: '会话记忆', label_char_budget: '上下文字符预算',
    label_keep_recent: '保留最近轮次', label_summary_ratio: '摘要占比',
    label_recall_max: '记忆召回上限', label_recall_min_score: '最低记忆匹配度',
    section_tools_config: '工具配置', label_tools_enabled: '工具总开关',
    web_search_unsupported: '需要在 Cloud LLM 中配置一个支持联网的 provider（search: true），且 Cloud LLM 已启用',
    web_search_backend: '搜索方式', web_search_backend_ddg: 'DuckDuckGo（本地模型，无需 API Key）', web_search_backend_openai: '云兜底模型（需要配置支持联网的 provider）',
    label_voice_model: '语音模型', label_voice_lang: '语音语言',
    label_image_provider: '图像提供商', label_image_model: '图像模型',
    label_file_max_size: '最大文件大小(字节)', label_shell_timeout: 'Shell 超时(秒)', label_dispatch_strict: '外包子智能体只读模式（开启后禁止写文件和安装包）', label_agent_doc_scan: '系统能力定时扫描（自动更新 AI 对工具/智能体/技能的理解）',
    label_emb_top_k: '搜索结果数', label_emb_min_score: '最低相似度', label_emb_clustering: '聚类去重',
    section_triggers: '触发器', label_followup: '事件跟进', label_followup_importance: '最低重要性',
    label_followup_after: '跟进延迟(小时)', label_followup_max_age: '最大追溯(天)',
    label_strategy: '策略分析触发', label_idle: '闲时关心', label_idle_hours: '触发闲置(小时)',
  },
  en: {
    nav_chat: 'Chat', nav_profile: 'Profile', nav_system: 'System',
    loading: 'Loading...', load_error: 'Failed to load system info: ',
    section_overview: 'System Overview',
    section_tools: 'Built-in Tools',
    section_agents: 'Agents',
    section_skills: 'Skills',
    section_mcp: 'MCP Servers',
    empty_tools: 'No built-in tools', empty_agents: 'No agents configured', empty_skills: 'No skills yet', show_more: 'Show more', show_less: 'Show less',
    install_skill: 'Install', install_skill_tip: 'Install skill', install_skill_title: 'Install Skill',
    install_skill_desc: 'Paste YAML or SKILL.md content. Takes effect immediately.',
    install_skill_placeholder: 'Paste skill YAML or SKILL.md…', badge_file: 'Installed', badge_skillhub: 'SkillHub',
    tab_paste: 'Paste', tab_hub: 'SkillHub',
    hub_desc: 'Enter a skill name to fetch from SkillHub (e.g. explain-code).',
    hub_search_btn: 'Fetch', hub_searching: 'Searching…', hub_not_found: 'Skill not found. Try pasting SKILL.md content directly.',
    empty_mcp: 'No MCP servers',
    label_language: 'Language', label_llm_provider: 'LLM Provider',
    label_llm_model: 'LLM Model', label_llm_api: 'LLM API',
    label_llm_key: 'LLM API Key', label_telegram_token: 'Telegram Token',
    label_discord_token: 'Discord Token',
    label_embedding: 'Semantic Search', label_embedding_model: 'Embedding Model', label_cloud_llm: 'Cloud Fallback',
    label_public_mode: 'Public Access', label_proactive: 'Proactive Messages',
    label_tts: 'TTS', label_telegram: 'Telegram Bot',
    label_discord: 'Discord Bot', label_mcp: 'MCP',
    label_params: 'Params', label_keywords: 'Keywords',
    label_schedule: 'Schedule', label_command: 'Command',
    no_key: 'no key configured',
    edit_confirm: 'OK', edit_cancel: 'Cancel',
    edit_placeholder: 'Enter new value', edit_placeholder_sensitive: 'Enter new key (leave empty to keep)',
    not_set: 'not set',
    badge_builtin: 'Built-in', badge_agent: 'Agent', badge_skill: 'Skill', badge_mcp: 'MCP',
    on: 'ON', off: 'OFF', toggle_theme: 'Toggle theme', toggle_click: 'Click to toggle',
    restart_timeout: 'Restart timed out. Please refresh manually.', err_failed: 'Failed: ',
    banner_msg: 'Config changed — restart required', btn_restart: 'Restart now', btn_revert: 'Revert', btn_cancel: 'Cancel', btn_install: 'Install',
    restarting: 'Restarting...', reverting: 'Reverting...',
    label_temperature: 'Temperature', label_max_tokens: 'Max Tokens', label_temp_dir: 'Temp Dir',
    label_allowed_ids: 'Allowed User IDs', label_voice_zh: 'Chinese Voice', label_voice_en: 'English Voice',
    label_max_chars: 'Max Chars', label_api_base: 'API Base',
    label_interval: 'Interval (min)', label_quiet_start: 'Quiet Start', label_quiet_end: 'Quiet End',
    label_max_per_day: 'Max/Day', label_min_gap: 'Min Gap (min)', label_access_token: 'Access Token',
    label_bot_token: 'Bot Token',
    section_llm: 'Primary LLM', section_telegram: 'Telegram Bot', section_discord: 'Discord Bot',
    section_tts_config: 'TTS Config', section_embedding_config: 'Semantic Search Config',
    section_proactive_config: 'Proactive Config', section_public_config: 'Public Access Config',
    hint_allowed_ids: 'Empty=everyone, comma-separated IDs',
    confirm_delete: 'Delete "{name}"? This cannot be undone.',
    delete_tip: 'Delete',
    add_provider: 'Add Provider', label_new_name: 'Name', label_new_model: 'Model', label_new_base: 'API Base',
    label_priority: 'Priority', label_search: 'Web Search',
    label_escalation_auto: 'Auto Fallback', label_escalation_feedback: 'Notify User on Fallback',
    label_escalation_min_length: 'Min Response Length',
    section_cloud_providers: 'Providers', section_cloud_escalation: 'Fallback Strategy',
    provider_no_key: 'no key set',
    label_timezone: 'Timezone',
    section_database: 'Database', label_db_name: 'DB Name', label_db_user: 'User', label_db_host: 'Host',
    section_session_memory: 'Session Memory', label_char_budget: 'Context Budget (chars)',
    label_keep_recent: 'Keep Recent Turns', label_summary_ratio: 'Summary Ratio',
    label_recall_max: 'Max Memory Recall', label_recall_min_score: 'Min Memory Match Score',
    section_tools_config: 'Tools Config', label_tools_enabled: 'Tools Enabled',
    web_search_unsupported: 'Requires a Cloud LLM provider with search: true configured and Cloud LLM enabled',
    web_search_backend: 'Search backend', web_search_backend_ddg: 'DuckDuckGo (local model, no API key)', web_search_backend_openai: 'Cloud Fallback (requires a provider with search enabled)',
    label_voice_model: 'Voice Model', label_voice_lang: 'Voice Language',
    label_image_provider: 'Image Provider', label_image_model: 'Image Model',
    label_file_max_size: 'Max File Size (bytes)', label_shell_timeout: 'Shell Timeout (s)', label_dispatch_strict: 'Outsource Sub-Agent Read-Only Mode (when on, disables file writes and package installs)', label_agent_doc_scan: 'Scheduled System Capability Scan (auto-updates AI knowledge of tools/agents/skills)',
    label_emb_top_k: 'Max Results', label_emb_min_score: 'Min Score', label_emb_clustering: 'Cluster Dedup',
    section_triggers: 'Triggers', label_followup: 'Event Follow-up', label_followup_importance: 'Min Importance',
    label_followup_after: 'Follow-up Delay (hrs)', label_followup_max_age: 'Max Age (days)',
    label_strategy: 'Strategy Analysis', label_idle: 'Idle Check-in', label_idle_hours: 'Idle Hours',
  },
  ja: {
    nav_chat: 'Chat', nav_profile: 'プロフィール', nav_system: 'システム',
    loading: '読み込み中...', load_error: 'システム情報の読み込みに失敗: ',
    section_overview: 'システム概要',
    section_tools: '組み込みツール',
    section_agents: 'エージェント',
    section_skills: 'スキル',
    section_mcp: 'MCPサーバー',
    empty_tools: '組み込みツールなし', empty_agents: 'エージェント未設定', empty_skills: 'スキルなし', show_more: '展開', show_less: '折りたたむ',
    install_skill: 'インストール', install_skill_tip: 'スキルをインストール', install_skill_title: 'スキルのインストール',
    install_skill_desc: 'YAMLまたはSKILL.md形式を貼り付けてください。インストール後すぐに有効になります。',
    install_skill_placeholder: 'スキル YAMLまたはSKILL.mdを貼り付け…', badge_file: 'インストール済', badge_skillhub: 'SkillHub',
    tab_paste: '貼り付け', tab_hub: 'SkillHub',
    hub_desc: 'スキル名を入力してSkillHubから取得（例: explain-code）。',
    hub_search_btn: '取得', hub_searching: '検索中…', hub_not_found: 'スキルが見つかりません。SKILL.mdの内容を直接貼り付けてください。',
    empty_mcp: 'MCPサーバーなし',
    label_language: '言語', label_llm_provider: 'LLMプロバイダー',
    label_llm_model: 'LLMモデル', label_llm_api: 'LLM API',
    label_llm_key: 'LLM APIキー', label_telegram_token: 'Telegram Token',
    label_discord_token: 'Discord Token',
    label_embedding: 'セマンティック検索', label_embedding_model: '埋め込みモデル', label_cloud_llm: 'クラウドフォールバック',
    label_public_mode: '公開アクセス', label_proactive: 'プロアクティブ通知',
    label_tts: '音声合成', label_telegram: 'Telegram Bot',
    label_discord: 'Discord Bot', label_mcp: 'MCP',
    label_params: 'パラメータ', label_keywords: 'キーワード',
    label_schedule: 'スケジュール', label_command: 'コマンド',
    no_key: 'キー未設定',
    edit_confirm: '確認', edit_cancel: 'キャンセル',
    edit_placeholder: '新しい値を入力', edit_placeholder_sensitive: '新しいキーを入力（空欄で変更なし）',
    not_set: '未設定',
    badge_builtin: '組み込み', badge_agent: 'エージェント', badge_skill: 'スキル', badge_mcp: 'MCP',
    on: 'ON', off: 'OFF', toggle_theme: 'テーマ切替', toggle_click: 'クリックで切替',
    restart_timeout: '再起動がタイムアウトしました。手動でリフレッシュしてください。', err_failed: '失敗: ',
    banner_msg: '設定が変更されました — 再起動が必要です', btn_restart: '今すぐ再起動', btn_revert: '元に戻す', btn_cancel: 'キャンセル', btn_install: 'インストール',
    restarting: '再起動中...', reverting: '元に戻し中...',
    label_temperature: '温度', label_max_tokens: '最大トークン', label_temp_dir: '一時ディレクトリ',
    label_allowed_ids: '許可ユーザーID', label_voice_zh: '中国語音声', label_voice_en: '英語音声',
    label_max_chars: '最大文字数', label_api_base: 'APIアドレス',
    label_interval: '間隔(分)', label_quiet_start: '静寂開始', label_quiet_end: '静寂終了',
    label_max_per_day: '1日最大数', label_min_gap: '最小間隔(分)', label_access_token: 'アクセストークン',
    label_bot_token: 'Bot Token',
    section_llm: 'メイン LLM', section_telegram: 'Telegram Bot', section_discord: 'Discord Bot',
    section_tts_config: '音声合成設定', section_embedding_config: 'セマンティック検索設定',
    section_proactive_config: 'プロアクティブ設定', section_public_config: '公開アクセス設定',
    hint_allowed_ids: '空=全員、カンマ区切りID',
    confirm_delete: '「{name}」を削除しますか？この操作は元に戻せません。',
    delete_tip: '削除',
    add_provider: 'プロバイダー追加', label_new_name: '名前', label_new_model: 'モデル', label_new_base: 'APIアドレス',
    label_priority: '優先度', label_search: 'ウェブ検索',
    label_escalation_auto: '自動フォールバック', label_escalation_feedback: 'フォールバック時通知',
    label_escalation_min_length: '最小回答文字数',
    section_cloud_providers: 'プロバイダー設定', section_cloud_escalation: 'フォールバック設定',
    provider_no_key: 'キー未設定',
    label_timezone: 'タイムゾーン',
    section_database: 'データベース', label_db_name: 'DB名', label_db_user: 'ユーザー', label_db_host: 'ホスト',
    section_session_memory: 'セッションメモリ', label_char_budget: 'コンテキスト予算(文字)',
    label_keep_recent: '保持ターン数', label_summary_ratio: '要約比率',
    label_recall_max: '最大記憶召回数', label_recall_min_score: '最小記憶マッチスコア',
    section_tools_config: 'ツール設定', label_tools_enabled: 'ツール有効',
    web_search_unsupported: 'Cloud LLM で search: true のプロバイダーを設定し、Cloud LLM を有効にしてください',
    web_search_backend: '検索方式', web_search_backend_ddg: 'DuckDuckGo（ローカルモデル、APIキー不要）', web_search_backend_openai: 'クラウドフォールバック（検索対応プロバイダーが必要）',
    label_voice_model: '音声モデル', label_voice_lang: '音声言語',
    label_image_provider: '画像プロバイダー', label_image_model: '画像モデル',
    label_file_max_size: '最大ファイルサイズ(bytes)', label_shell_timeout: 'Shellタイムアウト(秒)', label_dispatch_strict: '外注サブエージェント読み取り専用モード（オンでファイル書込・パッケージ導入を禁止）', label_agent_doc_scan: 'システム能力定期スキャン（ツール/エージェント/スキルのAI理解を自動更新）',
    label_emb_top_k: '最大結果数', label_emb_min_score: '最小スコア', label_emb_clustering: 'クラスタ重複排除',
    section_triggers: 'トリガー', label_followup: 'イベントフォロー', label_followup_importance: '最小重要度',
    label_followup_after: 'フォロー待機時間(時間)', label_followup_max_age: '最大追跡日数',
    label_strategy: '戦略分析トリガー', label_idle: '無応答時確認', label_idle_hours: '無応答判定時間(時間)',
  },
};

function detectLang() {
  const saved = localStorage.getItem(LANG_KEY);
  if (saved && I18N[saved]) return saved;
  const br = navigator.language || '';
  if (br.startsWith('zh')) return 'zh';
  if (br.startsWith('ja')) return 'ja';
  return 'en';
}

let currentLang = detectLang();
let _data = null;

function t(key) { return (I18N[currentLang] || I18N.en)[key] || key; }

function setLang(lang) {
  currentLang = lang;
  localStorage.setItem(LANG_KEY, lang);
  document.querySelectorAll('.lang-btn').forEach(b =>
    b.classList.toggle('active', b.textContent === { zh:'中文', en:'EN', ja:'日本語' }[lang]));
  document.getElementById('nav-chat').textContent = t('nav_chat');
  document.getElementById('nav-profile').textContent = t('nav_profile');
  document.getElementById('nav-system').textContent = t('nav_system');
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) themeBtn.title = t('toggle_theme');
  const hubInput = document.getElementById('hubSkillName');
  if (hubInput) hubInput.placeholder = t('hub_placeholder') || 'explain-code';
  const titleText = '⚙ ' + t('nav_system') + ' — ' + DB_NAME;
  document.getElementById('header-title').textContent = titleText;
  document.title = t('nav_system') + ' — ' + DB_NAME;
  if (_data) render(_data);
}

function getDeviceToken() {
  const m = document.cookie.match(/(?:^|;\s*)jkriver_token=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : '';
}
function authHeaders() {
  const h = {};
  const tk = getDeviceToken();
  if (tk) h['X-Device-Token'] = tk;
  return h;
}
function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function _mask(v) {
  if (!v) return '';
  if (v.length <= 8) return '••••';
  return v.slice(0,6) + '••••' + v.slice(-4);
}

function badge(type) {
  const map = { builtin: 'badge-builtin', agent: 'badge-agent', mcp: 'badge-mcp', skill: 'badge-skill' };
  const label = { builtin: t('badge_builtin'), agent: t('badge_agent'), mcp: t('badge_mcp'), skill: t('badge_skill') };
  return `<span class="badge ${map[type] || 'badge-builtin'}">${label[type] || type}</span>`;
}
function statusBadge(enabled) {
  return enabled
    ? `<span class="badge badge-on">${t('on')}</span>`
    : `<span class="badge badge-off">${t('off')}</span>`;
}
function toggleBadge(type, name, enabled) {
  const cls = enabled ? 'badge-on' : 'badge-off';
  return `<span class="badge ${cls} toggle-badge" style="cursor:pointer" data-type="${escHtml(type)}" data-name="${escHtml(name)}" data-enabled="${enabled}" title="${t('toggle_click')}" onclick="handleToggle(this)">` +
    (enabled ? t('on') : t('off')) + `</span>`;
}
