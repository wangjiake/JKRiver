async function toggleConfig(el) {
  if (el.classList.contains('editing')) return;
  const path = el.dataset.path;
  const currentOn = el.dataset.current === 'true';
  const newOn = !currentOn;
  el.style.opacity = '0.6';
  el.style.pointerEvents = 'none';
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/system/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ path, value: String(newOn) }),
    });
    if (!res.ok) throw new Error(await res.text());
    el.dataset.current = String(newOn);
    const valueEl = el.querySelector('.value span, .config-field-value');
    if (valueEl) {
      valueEl.textContent = newOn ? t('on') : t('off');
      valueEl.className = (el.classList.contains('config-field') ? 'config-field-value' : 'value') + ` ${newOn ? 'on' : 'off'}`;
    }
    showBanner();
  } catch(err) {
    alert('Failed: ' + err.message);
  } finally {
    el.style.opacity = '';
    el.style.pointerEvents = '';
  }
}

function toggleCp(idx) {
  const card = document.getElementById('cp-' + idx);
  card.classList.toggle('open');
}


async function addCloudProvider() {
  const name  = document.getElementById('cp-new-name').value.trim();
  const model = document.getElementById('cp-new-model').value.trim();
  const base  = document.getElementById('cp-new-base').value.trim();
  if (!name || !model) { alert(t('label_new_name') + ' / ' + t('label_new_model') + ' required'); return; }
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/system/cloud_provider`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ name, model, api_base: base }),
    });
    if (!res.ok) throw new Error(await res.text());
    showBanner(); load({ silent: true });
  } catch(err) { alert('Failed: ' + err.message); }
}

async function selectChoice(btn) {
  const field = btn.closest('.config-field');
  const path = field.dataset.path;
  const value = btn.dataset.value;
  if (field.dataset.current === value) return;
  field.querySelectorAll('.choice-btn').forEach(b => b.disabled = true);
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/system/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ path, value }),
    });
    if (!res.ok) throw new Error(await res.text());
    field.dataset.current = value;
    field.querySelectorAll('.choice-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.value === value);
      b.disabled = false;
    });
    showBanner();
  } catch(e) {
    alert('Failed: ' + e.message);
    field.querySelectorAll('.choice-btn').forEach(b => b.disabled = false);
  }
}

async function selectInfoChoice(btn) {
  const card = btn.closest('.info-card');
  const path = card.dataset.path;
  const value = btn.dataset.value;
  if (card.dataset.current === value) return;
  card.querySelectorAll('.choice-btn').forEach(b => b.disabled = true);
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/system/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ path, value }),
    });
    if (!res.ok) throw new Error(await res.text());
    card.dataset.current = value;
    card.querySelectorAll('.choice-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.value === value);
      b.disabled = false;
    });
    showBanner();
  } catch(e) {
    alert('Failed: ' + e.message);
    card.querySelectorAll('.choice-btn').forEach(b => b.disabled = false);
  }
}

function startConfigEdit(field) {
  if (field.classList.contains('editing')) return;
  field.classList.add('editing');
  const path = field.dataset.path;
  const sensitive = field.dataset.sensitive === 'true';
  const current = field.dataset.current;
  const options = field.dataset.options ? JSON.parse(field.dataset.options) : null;
  const valueDiv = field.querySelector('.config-field-value');

  let inputHtml;
  if (options) {
    inputHtml = `<select class="edit-input">${options.map(o => `<option value="${escHtml(o)}"${o===current?' selected':''}>${escHtml(o)}</option>`).join('')}</select>`;
  } else if (sensitive) {
    inputHtml = `<input class="edit-input" type="password" placeholder="${t('edit_placeholder_sensitive')}">`;
  } else {
    inputHtml = `<input class="edit-input" type="text" value="${escHtml(current)}">`;
  }

  valueDiv.innerHTML = inputHtml +
    `<div class="edit-actions">
      <button class="edit-btn confirm" onclick="confirmConfigEdit(event,this.closest('.config-field'))">${t('edit_confirm')}</button>
      <button class="edit-btn cancel" onclick="cancelConfigEdit(event,this.closest('.config-field'))">${t('edit_cancel')}</button>
    </div>`;

  const inp = valueDiv.querySelector('.edit-input');
  inp.focus();
  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter') confirmConfigEdit(e, field);
    if (e.key === 'Escape') cancelConfigEdit(e, field);
  });
}

async function confirmConfigEdit(e, field) {
  e.stopPropagation();
  const path = field.dataset.path;
  const sensitive = field.dataset.sensitive === 'true';
  const inp = field.querySelector('.edit-input');
  const value = inp.value.trim();
  if (sensitive && !value) { cancelConfigEdit(e, field); return; }
  const btn = field.querySelector('.edit-btn.confirm');
  btn.disabled = true;
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/system/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ path, value }),
    });
    if (!res.ok) throw new Error(await res.text());
    const display = sensitive ? _mask(value) : value;
    field.dataset.current = sensitive ? display : value;
    field.querySelector('.config-field-value').innerHTML = `${escHtml(display) || '—'}`;
    field.classList.remove('editing');
    showBanner();
  } catch(err) {
    alert('Failed: ' + err.message);
    btn.disabled = false;
  }
}

function cancelConfigEdit(e, field) {
  e.stopPropagation();
  const current = field.dataset.current;
  field.querySelector('.config-field-value').innerHTML = `${escHtml(current) || '—'}`;
  field.classList.remove('editing');
}

function startEdit(card) {
  if (card.classList.contains('editing')) return;
  card.classList.add('editing');
  const path = card.dataset.path;
  const sensitive = card.dataset.sensitive === 'true';
  const current = card.dataset.current;
  const options = card.dataset.options ? JSON.parse(card.dataset.options) : null;
  const valueDiv = card.querySelector('.value');

  let inputHtml;
  if (options) {
    inputHtml = `<select class="edit-input">${options.map(o => `<option value="${escHtml(o)}"${o===current?' selected':''}>${escHtml(o)}</option>`).join('')}</select>`;
  } else if (sensitive) {
    inputHtml = `<input class="edit-input" type="password" placeholder="${t('edit_placeholder_sensitive')}">`;
  } else {
    inputHtml = `<input class="edit-input" type="text" value="${escHtml(current)}">`;
  }

  valueDiv.innerHTML = inputHtml +
    `<div class="edit-actions">
      <button class="edit-btn confirm" onclick="confirmEdit(event,this.closest('.info-card'))">${t('edit_confirm')}</button>
      <button class="edit-btn cancel" onclick="cancelEdit(event,this.closest('.info-card'))">${t('edit_cancel')}</button>
    </div>`;

  const inp = valueDiv.querySelector('.edit-input');
  inp.focus();
  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter') confirmEdit(e, card);
    if (e.key === 'Escape') cancelEdit(e, card);
  });
}

async function confirmEdit(e, card) {
  e.stopPropagation();
  const path = card.dataset.path;
  const sensitive = card.dataset.sensitive === 'true';
  const inp = card.querySelector('.edit-input');
  const value = inp.value.trim();
  if (sensitive && !value) { cancelEdit(e, card); return; }

  const btn = card.querySelector('.edit-btn.confirm');
  btn.disabled = true;
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/system/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ path, value }),
    });
    if (!res.ok) throw new Error(await res.text());
    // Update displayed value
    const display = sensitive ? _mask(value) : value;
    card.dataset.current = sensitive ? display : value;
    card.querySelector('.value').innerHTML = `<span>${escHtml(display) || '—'}</span>`;
    card.classList.remove('editing');
    showBanner();
  } catch(err) {
    alert('Failed: ' + err.message);
    btn.disabled = false;
  }
}

function cancelEdit(e, card) {
  e.stopPropagation();
  const current = card.dataset.current;
  const onClass = card.dataset.on === 'true' ? 'on' : card.dataset.on === 'false' ? 'off' : '';
  card.querySelector('.value').innerHTML = `<span class="${onClass}">${escHtml(current) || '—'}</span>`;
  card.classList.remove('editing');
}

async function setWebSearchBackend(backend) {
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/system/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ path: 'tools.web_search.backend', value: backend }),
    });
    if (!res.ok) throw new Error(await res.text());
    showBanner();
  } catch(e) { console.error(e); }
}

// Toggle handler (called directly via onclick attribute)
async function handleToggle(badge) {
  const type = badge.dataset.type;
  const name = badge.dataset.name;
  const currentEnabled = badge.dataset.enabled === 'true';
  const newEnabled = !currentEnabled;
  badge.style.opacity = '0.5';
  badge.style.pointerEvents = 'none';
  try {
    const res = await fetch(`http://${location.hostname}:${API_PORT}/system/${type}/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ enabled: newEnabled }),
    });
    if (!res.ok) throw new Error(await res.text());
    const json = await res.json();
    badge.dataset.enabled = String(newEnabled);
    badge.textContent = newEnabled ? t('on') : t('off');
    badge.className = `badge ${newEnabled ? 'badge-on' : 'badge-off'} toggle-badge`;
    const eid = encodeURIComponent(name);
    const card = document.getElementById(`card-${type}-${eid}`);
    if (card) card.classList.toggle('disabled', !newEnabled);
    if (json.pending_restart) showBanner();
  } catch(e) {
    alert('Failed: ' + e.message);
  } finally {
    badge.style.opacity = '';
    badge.style.pointerEvents = '';
  }
}

// Delete event delegation
document.getElementById('content').addEventListener('click', async function(e) {
  const btn = e.target.closest('.delete-btn');
  if (!btn) return;
  e.stopPropagation();
  const type = btn.dataset.type;
  const name = btn.dataset.name;
  const msg = t('confirm_delete').replace('{name}', name);
  if (!confirm(msg)) return;
  btn.disabled = true;
  btn.style.opacity = '0.4';
  try {
    const endpoint = type === 'skill-file'
      ? `http://${location.hostname}:${API_PORT}/system/skill/${encodeURIComponent(name)}`
      : `http://${location.hostname}:${API_PORT}/system/${type}/${encodeURIComponent(name)}`;
    const res = await fetch(endpoint, { method: 'DELETE', headers: authHeaders() });
    if (!res.ok) throw new Error(await res.text());
    const json = await res.json();
    if (type === 'cloud_provider') {
      showBanner(); load({ silent: true });
    } else {
      const eid = encodeURIComponent(name);
      const cardType = type === 'skill-file' ? 'skill' : type;
      const card = document.getElementById(`card-${cardType}-${eid}`);
      if (card) card.remove();
      if (json.pending_restart) showBanner();
    }
  } catch(err) {
    alert('Failed: ' + err.message);
    btn.disabled = false;
    btn.style.opacity = '';
  }
});
