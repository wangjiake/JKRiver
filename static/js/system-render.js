function renderInfoCard(r) {
  const onClass = r.on === true ? 'on' : r.on === false ? 'off' : '';
  // Choice buttons card
  if (r.choice) {
    const btns = r.options.map(o =>
      `<button class="choice-btn${String(r.value) === String(o) ? ' active' : ''}" data-value="${escHtml(o)}" onclick="selectInfoChoice(this)">${escHtml(o)}</button>`
    ).join('');
    return `
    <div class="info-card" data-path="${escHtml(r.path)}" data-current="${escHtml(r.value)}">
      <div class="label">${t(r.key)}</div>
      <div class="value"><div class="choice-group">${btns}</div></div>
    </div>`;
  }
  // Boolean toggle card (ON/OFF clickable)
  if (r.toggle) {
    const curOn = r.on;
    const badgeCls = curOn ? 'badge-on' : 'badge-off';
    const badgeTxt = curOn ? t('on') : t('off');
    return `
    <div class="info-card editable" data-path="${escHtml(r.path)}" data-current="${curOn}" onclick="toggleConfig(this)">
      <div class="label">${t(r.key)}<span class="edit-icon">✎</span></div>
      <div class="value"><span class="badge ${badgeCls}">${badgeTxt}</span></div>
    </div>`;
  }
  // Read-only card
  if (!r.editable) {
    return `
    <div class="info-card">
      <div class="label">${t(r.key)}</div>
      <div class="value ${onClass}">${escHtml(r.value)}</div>
    </div>`;
  }
  // Text / dropdown / sensitive edit card
  const optionsAttr = r.options ? ` data-options='${JSON.stringify(r.options)}'` : '';
  return `
    <div class="info-card editable" data-path="${escHtml(r.path)}" data-sensitive="${r.sensitive ? 'true' : 'false'}" data-current="${escHtml(r.value)}"${optionsAttr} onclick="startEdit(this)">
      <div class="label">${t(r.key)}<span class="edit-icon">✎</span></div>
      <div class="value ${onClass}"><span>${escHtml(r.value) || '—'}</span></div>
    </div>`;
}

function renderConfigField(f) {
  if (f.choice) {
    const btns = f.options.map(o =>
      `<button class="choice-btn${String(f.value) === String(o) ? ' active' : ''}" data-value="${escHtml(o)}" onclick="selectChoice(this)">${escHtml(f.labels ? f.labels[o] : o)}</button>`
    ).join('');
    return `<div class="config-field" data-path="${escHtml(f.path)}" data-current="${escHtml(f.value)}">
      <div class="config-field-label">${t(f.labelKey)}</div>
      <div class="config-field-value"><div class="choice-group">${btns}</div></div>
    </div>`;
  }
  if (f.separator) {
    return `<div style="padding:6px 16px 4px; font-size:11px; font-weight:600; color:var(--accent); background:var(--bg-input); border-bottom:1px solid var(--border-light); text-transform:uppercase; letter-spacing:0.06em">${escHtml(f.label)}</div>`;
  }
  if (f.toggle) {
    const cls = f.on ? 'on' : 'off';
    return `<div class="config-field editable" data-path="${escHtml(f.path)}" data-current="${f.on}" onclick="toggleConfig(this)">
      <div class="config-field-label">${t(f.labelKey)}</div>
      <div class="config-field-value ${cls}">${f.on ? t('on') : t('off')}</div>
    </div>`;
  }
  if (!f.path) {
    return `<div class="config-field">
      <div class="config-field-label">${t(f.labelKey)}</div>
      <div class="config-field-value">${escHtml(f.value) || '—'}</div>
    </div>`;
  }
  const optAttr = f.options ? ` data-options='${JSON.stringify(f.options)}'` : '';
  return `<div class="config-field editable" data-path="${escHtml(f.path)}" data-sensitive="${f.sensitive ? 'true' : 'false'}" data-current="${escHtml(f.value)}"${optAttr} onclick="startConfigEdit(this)">
    <div class="config-field-label">${t(f.labelKey)}</div>
    <div class="config-field-value">${escHtml(f.value) || '—'}${f.hint ? `<div class="config-field-hint">${t(f.hint)}</div>` : ''}</div>
  </div>`;
}

function renderConfigSection(cfg) {
  const open = cfg.open ? 'open' : '';
  return `<div class="config-section ${open}" id="cs-${cfg.id}">
    <div class="config-section-header" onclick="toggleSection('${cfg.id}')">
      <div class="config-section-title">${t(cfg.titleKey)}</div>
      ${cfg.statusBadge || ''}
      <span class="config-section-arrow">&#9658;</span>
    </div>
    <div class="config-section-body">
      ${cfg.fields.map(renderConfigField).join('')}
    </div>
  </div>`;
}

function toggleSection(id) {
  document.getElementById('cs-' + id).classList.toggle('open');
}

function renderCloudSection(sys, cloudProviders) {
  const providersHtml = (cloudProviders || []).map((p, idx) => {
    const hasKey = !!p.api_key_masked;
    const keyBadge = hasKey ? `<span class="badge badge-on" style="font-size:10px">KEY</span>`
                            : `<span class="badge badge-off" style="font-size:10px">NO KEY</span>`;
    const priBadge = `<span class="badge" style="background:var(--bg-hover);color:var(--text-faint);font-size:10px">P${escHtml(p.priority)}</span>`;
    const fields = [
      { labelKey: 'label_llm_model',   value: p.model,                             path: `cloud_llm.providers.${idx}.model` },
      { labelKey: 'label_llm_api',     value: p.api_base,                          path: `cloud_llm.providers.${idx}.api_base` },
      { labelKey: 'label_llm_key',     value: p.api_key_masked || '—',             path: `cloud_llm.providers.${idx}.api_key`, sensitive: true },
      { labelKey: 'label_temperature', value: p.temperature,                       path: `cloud_llm.providers.${idx}.temperature` },
      { labelKey: 'label_max_tokens',  value: p.max_tokens,                        path: `cloud_llm.providers.${idx}.max_tokens` },
      { labelKey: 'label_priority',    value: p.priority,                          path: `cloud_llm.providers.${idx}.priority` },
      { labelKey: 'label_search',      toggle: true, on: p.search,                 path: `cloud_llm.providers.${idx}.search` },
    ];
    return `<div class="cp-card" id="cp-${idx}">
      <div class="cp-header" onclick="toggleCp(${idx})">
        <span class="cp-name">${escHtml(p.name)}</span>
        <span class="cp-model">${escHtml(p.model)}</span>
        ${keyBadge}${priBadge}
        <button class="delete-btn" style="opacity:1" data-type="cloud_provider" data-name="${escHtml(p.name)}" title="${t('delete_tip')}">✕</button>
        <span class="cp-arrow">&#9658;</span>
      </div>
      <div class="cp-body">${fields.map(renderConfigField).join('')}</div>
    </div>`;
  }).join('');

  const addForm = `<div class="cp-add">
    <div class="cp-add-form hidden" id="cp-add-form">
      <input class="edit-input" id="cp-new-name"  placeholder="${t('label_new_name')}" style="flex:1;min-width:80px">
      <input class="edit-input" id="cp-new-model" placeholder="${t('label_new_model')}" style="flex:1;min-width:120px">
      <input class="edit-input" id="cp-new-base"  placeholder="${t('label_new_base')}" style="flex:2;min-width:180px">
      <button class="edit-btn confirm" onclick="addCloudProvider()">${t('edit_confirm')}</button>
      <button class="edit-btn cancel"  onclick="document.getElementById('cp-add-form').classList.add('hidden');document.getElementById('cp-add-btn').style.display=''">${t('edit_cancel')}</button>
    </div>
    <button class="cp-add-btn" id="cp-add-btn" onclick="this.style.display='none';document.getElementById('cp-add-form').classList.remove('hidden')">+ ${t('add_provider')}</button>
  </div>`;

  const sepStyle = `padding:6px 16px 4px;font-size:11px;font-weight:600;color:var(--accent);background:var(--bg-input);border-bottom:1px solid var(--border-light);text-transform:uppercase;letter-spacing:0.06em`;
  const escalation = [
    renderConfigField({ labelKey: 'label_escalation_auto',       toggle: true, on: sys.cloud_llm_escalation_auto,     path: 'cloud_llm.escalation.auto' }),
    renderConfigField({ labelKey: 'label_escalation_feedback',   toggle: true, on: sys.cloud_llm_escalation_feedback,  path: 'cloud_llm.escalation.feedback' }),
    renderConfigField({ labelKey: 'label_escalation_min_length', value: sys.cloud_llm_escalation_min_length,           path: 'cloud_llm.escalation.min_response_length' }),
  ].join('');

  const enableToggle = renderConfigField({ labelKey: 'label_cloud_llm', toggle: true, on: sys.cloud_llm_enabled, path: 'cloud_llm.enabled' });

  return `<div class="config-section" id="cs-cloud">
    <div class="config-section-header" onclick="toggleSection('cloud')">
      <div class="config-section-title">${t('label_cloud_llm')}</div>
      ${statusBadge(sys.cloud_llm_enabled)}
      <span class="config-section-arrow">&#9658;</span>
    </div>
    <div class="config-section-body">
      ${enableToggle}
      <div style="${sepStyle}">${t('section_cloud_providers')}</div>
      ${providersHtml}
      ${addForm}
      <div style="${sepStyle}">${t('section_cloud_escalation')}</div>
      ${escalation}
    </div>
  </div>`;
}

function renderSystem(sys, cloudProviders) {
  const provider = sys.llm_provider || 'openai';

  const topRows = [
    { key: 'label_language', value: sys.language, choice: true, path: 'language', options: ['en', 'zh', 'ja'] },
    { key: 'label_timezone', value: sys.timezone, editable: true, path: 'timezone' },
    { key: 'label_dispatch_strict', toggle: true, on: sys.dispatch_strict_mode, path: 'tools.dispatch_task.strict_mode' },
    { key: 'label_agent_doc_scan', toggle: true, on: sys.agent_doc_scan_enabled, path: 'agent_doc_scan.enabled' },
  ];

  const sections = [
    {
      id: 'llm', titleKey: 'section_llm', open: false,
      statusBadge: `<span class="badge badge-on" style="font-size:10px">${escHtml(sys.llm_model || provider)}</span>`,
      fields: [
        { labelKey: 'label_llm_provider', value: sys.llm_provider, path: 'llm_provider', choice: true, options: ['openai','local'], labels: { openai: '远端 API', local: '本地 Ollama' } },
        { separator: true, label: '远端 API (openai)' },
        { labelKey: 'label_llm_model',   value: sys.openai_model,          path: 'openai.model' },
        { labelKey: 'label_llm_api',     value: sys.openai_api_base,       path: 'openai.api_base' },
        { labelKey: 'label_llm_key',     value: sys.openai_api_key_masked || '—', path: 'openai.api_key', sensitive: true },
        { labelKey: 'label_temperature', value: sys.openai_temperature,    path: 'openai.temperature' },
        { labelKey: 'label_max_tokens',  value: sys.openai_max_tokens,     path: 'openai.max_tokens' },
        { separator: true, label: '本地 Ollama (local)' },
        { labelKey: 'label_llm_model',   value: sys.local_model,           path: 'local.model' },
        { labelKey: 'label_llm_api',     value: sys.local_api_base,        path: 'local.api_base' },
        { labelKey: 'label_temperature', value: sys.local_temperature,     path: 'local.temperature' },
        { labelKey: 'label_max_tokens',  value: sys.local_max_tokens,      path: 'local.max_tokens' },
      ],
    },
    {
      id: 'telegram', titleKey: 'section_telegram',
      statusBadge: statusBadge(sys.telegram_enabled),
      fields: [
        { labelKey: 'label_enabled',     toggle: true, on: sys.telegram_enabled,           path: 'telegram.enabled' },
        { labelKey: 'label_bot_token',   value: sys.telegram_token_masked || '—', path: 'telegram.bot_token', sensitive: true },
        { labelKey: 'label_allowed_ids', value: sys.telegram_allowed_ids || '—',  path: 'telegram.allowed_user_ids', hint: 'hint_allowed_ids' },
        { labelKey: 'label_temp_dir',    value: sys.telegram_temp_dir,            path: 'telegram.temp_dir' },
      ],
    },
    {
      id: 'discord', titleKey: 'section_discord',
      statusBadge: statusBadge(sys.discord_enabled),
      fields: [
        { labelKey: 'label_enabled',     toggle: true, on: sys.discord_enabled,            path: 'discord.enabled' },
        { labelKey: 'label_bot_token',   value: sys.discord_token_masked || '—', path: 'discord.bot_token', sensitive: true },
        { labelKey: 'label_allowed_ids', value: sys.discord_allowed_ids || '—',  path: 'discord.allowed_user_ids', hint: 'hint_allowed_ids' },
        { labelKey: 'label_temp_dir',    value: sys.discord_temp_dir,            path: 'discord.temp_dir' },
      ],
    },
    {
      id: 'tts', titleKey: 'section_tts_config',
      statusBadge: statusBadge(sys.tts_enabled),
      fields: [
        { labelKey: 'label_tts',       toggle: true, on: sys.tts_enabled, path: 'tts.enabled' },
        { labelKey: 'label_voice_zh',  value: sys.tts_voice_zh,           path: 'tts.voices.zh' },
        { labelKey: 'label_voice_en',  value: sys.tts_voice_en,           path: 'tts.voices.en' },
        { labelKey: 'label_max_chars', value: sys.tts_max_chars,          path: 'tts.max_chars' },
        { labelKey: 'label_temp_dir',  value: sys.tts_temp_dir,           path: 'tts.temp_dir' },
      ],
    },
    {
      id: 'embedding', titleKey: 'section_embedding_config',
      statusBadge: statusBadge(sys.embedding_enabled),
      fields: [
        { labelKey: 'label_embedding',     toggle: true, on: sys.embedding_enabled, path: 'embedding.enabled' },
        { labelKey: 'label_llm_model',     value: sys.embedding_model,              path: 'embedding.model' },
        { labelKey: 'label_api_base',      value: sys.embedding_api_base,           path: 'embedding.api_base' },
        { labelKey: 'label_emb_top_k',     value: sys.embedding_top_k,              path: 'embedding.search.top_k' },
        { labelKey: 'label_emb_min_score', value: sys.embedding_min_score,          path: 'embedding.search.min_score' },
        { labelKey: 'label_emb_clustering',toggle: true, on: sys.embedding_clustering, path: 'embedding.clustering.enabled' },
      ],
    },
    {
      id: 'proactive', titleKey: 'section_proactive_config',
      statusBadge: statusBadge(sys.proactive_enabled),
      fields: [
        { labelKey: 'label_proactive',   toggle: true, on: sys.proactive_enabled, path: 'proactive.enabled' },
        { labelKey: 'label_interval',    value: sys.proactive_interval,            path: 'proactive.scan_interval_minutes' },
        { labelKey: 'label_quiet_start', value: sys.proactive_quiet_start,         path: 'proactive.quiet_hours.start' },
        { labelKey: 'label_quiet_end',   value: sys.proactive_quiet_end,           path: 'proactive.quiet_hours.end' },
        { labelKey: 'label_max_per_day', value: sys.proactive_max_per_day,         path: 'proactive.max_messages_per_day' },
        { labelKey: 'label_min_gap',     value: sys.proactive_min_gap,             path: 'proactive.min_gap_minutes' },
        { separator: true, label: t('section_triggers') },
        { labelKey: 'label_followup',          toggle: true, on: sys.proactive_followup_enabled,  path: 'proactive.triggers.event_followup.enabled' },
        { labelKey: 'label_followup_importance',value: sys.proactive_followup_min_importance,     path: 'proactive.triggers.event_followup.min_importance' },
        { labelKey: 'label_followup_after',    value: sys.proactive_followup_after_hours,          path: 'proactive.triggers.event_followup.followup_after_hours' },
        { labelKey: 'label_followup_max_age',  value: sys.proactive_followup_max_age,              path: 'proactive.triggers.event_followup.max_age_days' },
        { labelKey: 'label_strategy',    toggle: true, on: sys.proactive_strategy_enabled,  path: 'proactive.triggers.strategy.enabled' },
        { labelKey: 'label_idle',        toggle: true, on: sys.proactive_idle_enabled,      path: 'proactive.triggers.idle_checkin.enabled' },
        { labelKey: 'label_idle_hours',  value: sys.proactive_idle_hours,                   path: 'proactive.triggers.idle_checkin.idle_hours' },
      ],
    },
    {
      id: 'session_memory', titleKey: 'section_session_memory',
      statusBadge: '',
      fields: [
        { labelKey: 'label_char_budget',      value: sys.sm_char_budget,      path: 'session_memory.char_budget' },
        { labelKey: 'label_keep_recent',      value: sys.sm_keep_recent,      path: 'session_memory.keep_recent' },
        { labelKey: 'label_summary_ratio',    value: sys.sm_summary_ratio,    path: 'session_memory.summary_ratio' },
        { labelKey: 'label_recall_max',       value: sys.sm_recall_max,       path: 'session_memory.recall_max' },
        { labelKey: 'label_recall_min_score', value: sys.sm_recall_min_score, path: 'session_memory.recall_min_score' },
      ],
    },
    {
      id: 'tools_config', titleKey: 'section_tools_config',
      statusBadge: statusBadge(sys.tools_enabled),
      fields: [
        { labelKey: 'label_tools_enabled', toggle: true, on: sys.tools_enabled, path: 'tools.enabled' },
        { separator: true, label: 'voice_transcribe' },
        { labelKey: 'label_voice_model', value: sys.voice_model,    path: 'tools.voice_transcribe.model' },
        { labelKey: 'label_voice_lang',  value: sys.voice_language, path: 'tools.voice_transcribe.language' },
        { separator: true, label: 'image_describe' },
        { labelKey: 'label_image_provider', value: sys.image_provider, path: 'tools.image_describe.provider' },
        { labelKey: 'label_image_model',    value: sys.image_model,    path: 'tools.image_describe.model' },
        { separator: true, label: 'file_read' },
        { labelKey: 'label_file_max_size', value: sys.file_read_max_size, path: 'tools.file_read.max_file_size' },
        { separator: true, label: 'dispatch_task' },
        { labelKey: 'label_dispatch_strict', toggle: true, on: sys.dispatch_strict_mode, path: 'tools.dispatch_task.strict_mode' },
        { separator: true, label: 'shell_exec' },
        { labelKey: 'label_shell_timeout', value: sys.shell_timeout, path: 'tools.shell_exec.timeout' },
      ],
    },
    {
      id: 'public', titleKey: 'section_public_config',
      statusBadge: statusBadge(sys.public_mode),
      fields: [
        { labelKey: 'label_public_mode',  toggle: true, on: sys.public_mode,             path: 'public_mode.enabled' },
        { labelKey: 'label_access_token', value: sys.public_access_token_masked || '—',  path: 'public_mode.access_token', sensitive: true },
      ],
    },
    { _html: renderCloudSection(sys, cloudProviders) },
    {
      id: 'database', titleKey: 'section_database',
      statusBadge: '',
      fields: [
        { labelKey: 'label_db_name', value: sys.db_name },
        { labelKey: 'label_db_user', value: sys.db_user },
        { labelKey: 'label_db_host', value: sys.db_host },
      ],
    },
    {
      id: 'mcp', titleKey: 'section_mcp',
      statusBadge: statusBadge(sys.mcp_enabled),
      fields: [
        { labelKey: 'label_mcp', toggle: true, on: sys.mcp_enabled, path: 'mcp.enabled' },
      ],
    },
  ];

  return `
    <div class="info-grid" style="margin-bottom:14px">${topRows.map(renderInfoCard).join('')}</div>
    <div class="cards">${sections.map(s => s._html ? s._html : renderConfigSection(s)).join('')}</div>`;
}

function renderToolCard(tool) {
  const examples = tool.examples && tool.examples.length
    ? `<div class="card-examples">${tool.examples.map(e => `<span class="example-tag">${escHtml(e)}</span>`).join('')}</div>` : '';
  const params = Object.keys(tool.parameters || {}).length
    ? `<div class="card-meta">${t('label_params')}：<span>${Object.keys(tool.parameters).join(', ')}</span></div>` : '';
  const eid = encodeURIComponent(tool.name);
  const statusEl = tool.type === 'builtin'
    ? toggleBadge('tool', tool.name, tool.enabled)
    : statusBadge(tool.enabled);
  const warningEl = (tool.name === 'web_search' && tool.enabled && tool.search_supported === false)
    ? `<div style="margin-top:6px;padding:5px 8px;background:#2a2000;border:1px solid var(--yellow);border-radius:4px;color:var(--yellow);font-size:12px">⚠ ${t('web_search_unsupported')}</div>`
    : '';
  const backendEl = tool.name === 'web_search'
    ? `<div style="margin-top:8px;font-size:12px;">
        <div style="color:var(--text-muted);margin-bottom:4px;">${t('web_search_backend')}</div>
        <select style="width:100%;background:var(--bg-input);border:1px solid var(--border);color:var(--text-2);border-radius:4px;padding:4px 6px;font-size:12px;cursor:pointer;" onchange="setWebSearchBackend(this.value)">
          <option value="duckduckgo" ${tool.search_backend === 'duckduckgo' ? 'selected' : ''}>${t('web_search_backend_ddg')}</option>
          <option value="openai_responses" ${tool.search_backend === 'openai_responses' ? 'selected' : ''}>${t('web_search_backend_openai')}</option>
        </select>
      </div>`
    : '';
  return `
    <div class="card ${tool.enabled ? '' : 'disabled'}" id="card-tool-${eid}">
      <div class="card-header">
        <div class="card-name">${escHtml(tool.name)}</div>
        ${badge(tool.type)}${statusEl}
        ${tool.type === 'builtin' ? `<button class="delete-btn" data-type="tool" data-name="${escHtml(tool.name)}" title="${t('delete_tip')}">✕</button>` : ''}
      </div>
      <div class="card-collapsible collapsed">
        ${tool.description ? `<div class="card-desc">${escHtml(tool.description)}</div>` : ''}
        ${params}${examples}${backendEl}${warningEl}
      </div>
      <button class="card-expand-btn" onclick="expandCard(this)">▼ ${t('show_more')}</button>
    </div>`;
}

function renderAgentCard(a) {
  const examples = a.examples && a.examples.length
    ? `<div class="card-examples">${a.examples.map(e => `<span class="example-tag">${escHtml(e)}</span>`).join('')}</div>` : '';
  const eid = encodeURIComponent(a.name);
  return `
    <div class="card ${a.enabled ? '' : 'disabled'}" id="card-agent-${eid}">
      <div class="card-header">
        <div class="card-name">${escHtml(a.name)}</div>
        ${badge('agent')}
        <span class="badge" style="background:#1e2a1e;color:var(--green);font-size:10px">${escHtml(a.type)}</span>
        ${toggleBadge('agent', a.name, a.enabled)}
        <button class="delete-btn" data-type="agent" data-name="${escHtml(a.name)}" title="${t('delete_tip')}">✕</button>
      </div>
      <div class="card-collapsible collapsed">
        ${a.description ? `<div class="card-desc">${escHtml(a.description)}</div>` : ''}
        ${examples}
      </div>
      <button class="card-expand-btn" onclick="expandCard(this)">▼ ${t('show_more')}</button>
    </div>`;
}

function renderSkillCard(s) {
  const trigger = s.trigger_type === 'keyword'
    ? `${t('label_keywords')}：${s.keywords.slice(0,4).map(k => `<span class="example-tag">${escHtml(k)}</span>`).join('')}`
    : `${t('label_schedule')}：<span class="example-tag">${escHtml(s.cron)}</span>`;
  const eid = encodeURIComponent(s.name);
  const isSkillHub = s.source && s.source.startsWith('skillhub:');
  const isFile = s.source && s.source !== 'bundled' && !isSkillHub;
  const sourceBadge = isSkillHub
    ? `<span class="badge badge-skillhub">${t('badge_skillhub')}</span>`
    : isFile ? `<span class="badge badge-file">${t('badge_file')}</span>` : '';
  const deletable = isFile || isSkillHub;
  return `
    <div class="card ${s.enabled ? '' : 'disabled'}" id="card-skill-${eid}">
      <div class="card-header">
        <div class="card-name">${escHtml(s.name)}</div>
        ${badge('skill')}${sourceBadge}${toggleBadge('skill', s.name, s.enabled)}
        ${deletable ? `<button class="delete-btn" data-type="skill-file" data-name="${escHtml(s.name)}" title="${t('delete_tip')}">✕</button>` : ''}
      </div>
      <div class="card-collapsible collapsed">
        ${s.description ? `<div class="card-desc">${escHtml(s.description)}</div>` : ''}
        <div class="card-examples">${trigger}</div>
      </div>
      <button class="card-expand-btn" onclick="expandCard(this)">▼ ${t('show_more')}</button>
    </div>`;
}

function renderMCPCard(srv) {
  return `
    <div class="card">
      <div class="card-header">
        <div class="card-name">${escHtml(srv.name)}</div>
        ${badge('mcp')}
      </div>
      <div class="card-meta">${t('label_command')}：<span>${escHtml(srv.command)} ${escHtml((srv.args||[]).join(' '))}</span></div>
    </div>`;
}

function render(d) {
  if (d.pending_restart) showBanner(); else hideBanner();
  const tools = d.tools || [];
  const builtin = tools.filter(t => t.type === 'builtin');
  const mcpTools = tools.filter(t => t.type === 'mcp');
  const agents = d.agents || [];
  const skills = d.skills || [];
  const mcpServers = d.mcp_servers || [];

  document.getElementById('content').innerHTML = `
    <div class="section">
      <div class="section-title">${t('section_overview')}</div>
      ${renderSystem(d.system, d.cloud_providers || [])}
    </div>

    <div class="section">
      <div class="section-title">${t('section_tools')} (${builtin.filter(x=>x.enabled).length}/${builtin.length})</div>
      ${builtin.length ? `<div class="cards">${builtin.map(renderToolCard).join('')}</div>` : `<div class="empty">${t('empty_tools')}</div>`}
    </div>

    <div class="section">
      <div class="section-title">${t('section_agents')} (${agents.filter(a=>a.enabled).length}/${agents.length})</div>
      ${agents.length ? `<div class="cards">${agents.map(renderAgentCard).join('')}</div>` : `<div class="empty">${t('empty_agents')}</div>`}
    </div>

    <div class="section">
      <div class="section-title">
        ${t('section_skills')} (${skills.length})
        <button class="install-btn" onclick="openInstallSkill()" title="${t('install_skill_tip')}">+ ${t('install_skill')}</button>
      </div>
      ${skills.length ? `<div class="cards">${skills.map(renderSkillCard).join('')}</div>` : `<div class="empty">${t('empty_skills')}</div>`}
    </div>

    ${mcpServers.length || mcpTools.length ? `
    <div class="section">
      <div class="section-title">${t('section_mcp')}</div>
      ${mcpServers.length ? `<div class="cards">${mcpServers.map(renderMCPCard).join('')}</div>` : ''}
      ${mcpTools.length ? `<div class="cards" style="margin-top:12px">${mcpTools.map(renderToolCard).join('')}</div>` : ''}
    </div>` : ''}

    ${typeof renderFamilySection === 'function' ? renderFamilySection() : ''}
  `;
  requestAnimationFrame(applyCardCollapse);
  if (typeof refreshFamily === 'function') refreshFamily();
}

function expandCard(btn) {
  const card = btn.closest('.card');
  const body = card.querySelector('.card-collapsible');
  const expanded = !body.classList.contains('collapsed');
  if (expanded) {
    body.style.maxHeight = '';
    body.classList.add('collapsed');
    btn.textContent = '▼ ' + t('show_more');
  } else {
    body.classList.remove('collapsed');
    body.style.maxHeight = body.scrollHeight + 'px';
    btn.textContent = '▲ ' + t('show_less');
  }
}

function applyCardCollapse() {
  document.querySelectorAll('.card').forEach(card => {
    const body = card.querySelector('.card-collapsible');
    const btn = card.querySelector('.card-expand-btn');
    if (!body || !btn) return;
    // Temporarily expand to measure real height
    body.classList.remove('collapsed');
    body.style.maxHeight = 'none';
    const fullH = body.scrollHeight;
    if (fullH > 185) {
      body.classList.add('collapsed');
      body.style.maxHeight = '';
      card.classList.add('needs-collapse');
    } else {
      body.style.maxHeight = 'none';
      btn.style.display = 'none';
    }
  });
}
