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

// ── Send message ───────────────────────────────────────────────────────
function setSendStopMode(isStop) {
  const btn = document.getElementById('sendBtn');
  if (isStop) {
    btn.classList.add('stop-mode');
    btn.classList.remove('has-input');
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

function appendMessage(role, text, category, intent, at) {
  document.body.classList.remove('zero-state');
  try { localStorage.setItem(SESSION_ACTIVE_KEY, '1'); } catch (e) {}
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
