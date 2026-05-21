"""Server-side translations of every data-i18n key that appears in a template.

Mirrors the per-page I18N dicts in static/js/chat-i18n.js, profile.js,
system-i18n.js, and the inline blocks in templates/finance.html and
templates/health.html. The point is to eliminate the FOUC where the HTML
default text (usually English) flashes before the page's JS scanner swaps
in the user's chosen language. With this dict injected as `i18n` into every
template, we render `<span data-i18n="X">{{ i18n.X }}</span>` so the right
text is in place from the very first paint.

Client-side setLang() still runs and does the same data-i18n scan — that
keeps in-page language switching working without a reload. The server side
just makes sure the *initial* render is correct.

When you add a new data-i18n key to a template, add it here too (all three
locales) or the FOUC comes back for that one key.
"""

TEMPLATE_I18N = {
    'zh': {
        # ── Nav (shared by every page; also exposed via NAV_I18N for backwards compat) ──
        'nav_chat': '聊天', 'nav_profile': '个人资料', 'nav_tasks': '外包', 'nav_system': '系统',
        'db_label': '数据库',

        # ── chat.html ──
        'settings_title': '设置',
        'connecting': '连接中…',
        'placeholder': '输入消息…', 'send': '发送',
        'hint': 'Ctrl+Enter 发送 · Enter 换行',
        'history_title': '历史会话', 'history_label': '历史记录', 'pinned_label': '置顶',
        'new_chat': '+ 新建', 'new_session': '新建会话',
        'search_placeholder': '搜索…',
        'rename_title': '重命名会话', 'rename_placeholder': '输入名称…',
        'btn_cancel': '取消', 'btn_save': '保存',
        'section_session': '会话', 'session_label': '当前会话 ID',
        'section_sleep': '睡眠', 'auto_sleep': '定时睡眠',
        'mode_interval': '间隔', 'mode_daily': '定时',
        'every_label': '每', 'hours_label': '小时运行一次', 'at_label': '每天',
        'sleep_btn': '立即执行睡眠',
        'section_sys_stats': '系统状态', 'sys_stats_label': '状态栏显示系统信息',
        'sys_stats_sub': '显示 CPU / 内存 / 硬盘 / 网速', 'sys_stats_interval': '刷新间隔',
        'ss_cpu': 'CPU', 'ss_mem': '内存', 'ss_disk': '磁盘', 'ss_net': '网络',
        'section_token_usage': 'Token 用量',
        'token_today': '今天', 'token_week': '本周', 'token_month': '本月',
        'token_usage_label': '状态栏显示 Token 用量', 'token_usage_sub': '今天 / 本周 / 本月',
        'attach_title': '附加图片', 'voice_title': '语音输入',

        # ── profile.html ──
        'filter_title': '分类筛选', 'filter_all': '全部',
        'tab_profile': '当前画像', 'tab_timeline': '时间线', 'tab_snapshot': '月度快照',
        'tab_observations': '观察记录', 'tab_relationships': '人际关系',
        'loading': '加载中',
        'stat_sessions': '已处理会话', 'stat_observations': '观察记录',
        'stat_confirmed': '已确认', 'stat_suspected': '待确认',
        'stat_closed': '历史变迁', 'stat_disputes': '未解决矛盾',

        # ── system.html ──
        'toggle_theme': '切换主题',

        # ── finance.html ──
        'stat_total': '总支出 (JPY)', 'stat_count': '交易笔数',
        'stat_merchants': '商家数', 'stat_range': '时间范围',
        'tab_transactions': '交易记录', 'tab_monthly': '月度汇总',
        'tab_merchants': '商家排行', 'tab_categories': '分类统计',
        'tab_import': '导入', 'tab_mappings': '映射管理',
        'filter_year': '年:', 'filter_month': '月:',
        'filter_category': '分类:', 'filter_merchant': '商家:',
        'filter_search': '搜索...',
        'import_desc': '从 Gmail 导入消费通知邮件。增量导入只拉取最近交易日期之后的新邮件。',
        'import_after': '起始日期:', 'import_btn': '增量导入', 'import_all_btn': '全量导入',
        'map_pattern': '商家关键词', 'map_category': '分类', 'map_add': '添加',

        # ── health.html ──
        'stat_measures': '总测量数', 'stat_weight': '最新体重',
        'stat_activity_days': '活动天数', 'stat_sleep_days': '睡眠天数',
        'stat_avg_steps': '30天均步数', 'stat_avg_score': '30天睡眠评分',
        'tab_body': '体重/体组成', 'tab_activity': '活动', 'tab_sleep': '睡眠',
        'tab_trends': '趋势', 'tab_sync': '同步',
        'filter_days': '天数:',
    },
    'en': {
        'nav_chat': 'Chat', 'nav_profile': 'Profile', 'nav_tasks': 'Tasks', 'nav_system': 'System',
        'db_label': 'Database',

        'settings_title': 'Settings',
        'connecting': 'Connecting…',
        'placeholder': 'Type a message…', 'send': 'Send',
        'hint': 'Ctrl+Enter to send · Enter for new line',
        'history_title': 'History', 'history_label': 'History', 'pinned_label': 'Pinned',
        'new_chat': '+ New', 'new_session': 'New Session',
        'search_placeholder': 'Search…',
        'rename_title': 'Rename Session', 'rename_placeholder': 'Enter name…',
        'btn_cancel': 'Cancel', 'btn_save': 'Save',
        'section_session': 'Session', 'session_label': 'Current session ID',
        'section_sleep': 'Sleep', 'auto_sleep': 'Auto Sleep',
        'mode_interval': 'Interval', 'mode_daily': 'Daily',
        'every_label': 'Every', 'hours_label': 'hour(s)', 'at_label': 'At',
        'sleep_btn': 'Run Sleep Now',
        'section_sys_stats': 'System Stats', 'sys_stats_label': 'Show system info in status bar',
        'sys_stats_sub': 'CPU / Memory / Disk / Network speed', 'sys_stats_interval': 'Refresh interval',
        'ss_cpu': 'CPU', 'ss_mem': 'Memory', 'ss_disk': 'Disk', 'ss_net': 'Network',
        'section_token_usage': 'Token Usage',
        'token_today': 'Today', 'token_week': 'Week', 'token_month': 'Month',
        'token_usage_label': 'Show token usage in status bar', 'token_usage_sub': 'Today / This week / This month',
        'attach_title': 'Attach image', 'voice_title': 'Voice input',

        'filter_title': 'Filter', 'filter_all': 'All',
        'tab_profile': 'Profile', 'tab_timeline': 'Timeline', 'tab_snapshot': 'Snapshots',
        'tab_observations': 'Observations', 'tab_relationships': 'Relationships',
        'loading': 'Loading',
        'stat_sessions': 'Sessions', 'stat_observations': 'Observations',
        'stat_confirmed': 'Confirmed', 'stat_suspected': 'Suspected',
        'stat_closed': 'History', 'stat_disputes': 'Disputes',

        'toggle_theme': 'Toggle theme',

        'stat_total': 'Total (JPY)', 'stat_count': 'Transactions',
        'stat_merchants': 'Merchants', 'stat_range': 'Date Range',
        'tab_transactions': 'Transactions', 'tab_monthly': 'Monthly',
        'tab_merchants': 'Merchants', 'tab_categories': 'Categories',
        'tab_import': 'Import', 'tab_mappings': 'Mappings',
        'filter_year': 'Year:', 'filter_month': 'Month:',
        'filter_category': 'Category:', 'filter_merchant': 'Merchant:',
        'filter_search': 'Search...',
        'import_desc': 'Import transaction notifications from Gmail. Incremental import only fetches emails after the latest transaction date.',
        'import_after': 'After:', 'import_btn': 'Incremental Import', 'import_all_btn': 'Full Import',
        'map_pattern': 'Merchant pattern', 'map_category': 'Category', 'map_add': 'Add',

        'stat_measures': 'Measures', 'stat_weight': 'Latest Weight',
        'stat_activity_days': 'Activity Days', 'stat_sleep_days': 'Sleep Days',
        'stat_avg_steps': '30d Avg Steps', 'stat_avg_score': '30d Sleep Score',
        'tab_body': 'Body', 'tab_activity': 'Activity', 'tab_sleep': 'Sleep',
        'tab_trends': 'Trends', 'tab_sync': 'Sync',
        'filter_days': 'Days:',
    },
    'ja': {
        'nav_chat': 'チャット', 'nav_profile': 'プロフィール', 'nav_tasks': '派遣', 'nav_system': 'システム',
        'db_label': 'データベース',

        'settings_title': '設定',
        'connecting': '接続中…',
        'placeholder': 'メッセージを入力…', 'send': '送信',
        'hint': 'Ctrl+Enter で送信 · Enter で改行',
        'history_title': '履歴', 'history_label': '履歴', 'pinned_label': 'ピン留め',
        'new_chat': '+ 新規', 'new_session': '新しいセッション',
        'search_placeholder': '検索…',
        'rename_title': 'セッション名変更', 'rename_placeholder': '名前を入力…',
        'btn_cancel': 'キャンセル', 'btn_save': '保存',
        'section_session': 'セッション', 'session_label': '現在のセッション ID',
        'section_sleep': 'スリープ', 'auto_sleep': '自動スリープ',
        'mode_interval': '間隔', 'mode_daily': '毎日',
        'every_label': '毎', 'hours_label': '時間ごと', 'at_label': '毎日',
        'sleep_btn': '今すぐスリープ実行',
        'section_sys_stats': 'システム状態', 'sys_stats_label': 'ステータスバーにシステム情報を表示',
        'sys_stats_sub': 'CPU / メモリ / ディスク / 通信速度', 'sys_stats_interval': '更新間隔',
        'ss_cpu': 'CPU', 'ss_mem': 'メモリ', 'ss_disk': 'ディスク', 'ss_net': 'ネットワーク',
        'section_token_usage': 'Token 使用量',
        'token_today': '今日', 'token_week': '今週', 'token_month': '今月',
        'token_usage_label': 'ステータスバーにToken使用量を表示', 'token_usage_sub': '今日 / 今週 / 今月',
        'attach_title': '画像を添付', 'voice_title': '音声入力',

        'filter_title': 'カテゴリ', 'filter_all': 'すべて',
        'tab_profile': '現在のプロフィール', 'tab_timeline': 'タイムライン', 'tab_snapshot': '月別スナップショット',
        'tab_observations': '観察記録', 'tab_relationships': '人間関係',
        'loading': '読み込み中',
        'stat_sessions': '処理済み会話', 'stat_observations': '観察記録',
        'stat_confirmed': '確認済み', 'stat_suspected': '未確認',
        'stat_closed': '変遷履歴', 'stat_disputes': '未解決矛盾',

        'toggle_theme': 'テーマ切替',

        'stat_total': '総支出 (JPY)', 'stat_count': '取引件数',
        'stat_merchants': '加盟店数', 'stat_range': '期間',
        'tab_transactions': '取引一覧', 'tab_monthly': '月別集計',
        'tab_merchants': '加盟店ランキング', 'tab_categories': 'カテゴリ統計',
        'tab_import': 'インポート', 'tab_mappings': 'マッピング管理',
        'filter_year': '年:', 'filter_month': '月:',
        'filter_category': 'カテゴリ:', 'filter_merchant': '加盟店:',
        'filter_search': '検索...',
        'import_desc': 'Gmail からカード利用通知をインポート。増分インポートは最新取引日以降のメールのみ取得します。',
        'import_after': '開始日:', 'import_btn': '増分インポート', 'import_all_btn': 'フルインポート',
        'map_pattern': '加盟店パターン', 'map_category': 'カテゴリ', 'map_add': '追加',

        'stat_measures': '測定数', 'stat_weight': '最新体重',
        'stat_activity_days': '活動日数', 'stat_sleep_days': '睡眠日数',
        'stat_avg_steps': '30日平均歩数', 'stat_avg_score': '30日睡眠スコア',
        'tab_body': '体重/体組成', 'tab_activity': '活動', 'tab_sleep': '睡眠',
        'tab_trends': 'トレンド', 'tab_sync': '同期',
        'filter_days': '日数:',
    },
}
