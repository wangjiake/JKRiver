// Family Members section for the System page (industrial-grade revision).
//
// Concepts shown to the user:
//   Family Member  — an `accounts` row
//   Device         — an `access_tokens` row (token plaintext never displayed)
//   Invite link    — a `family_invites` UUID; admin sends the URL to family,
//                    family member opens it once on their device, the server
//                    mints a fresh device-bound token cookie automatically.
//
// UI never shows the raw token. The flow is:
//   1. admin clicks "Invite a family member" on a Member card
//   2. modal shows a one-time URL + Copy + (optional) QR
//   3. admin sends URL to the family member via any channel (WhatsApp etc.)
//   4. family member opens URL on their device, names it, accepts → logged in

const FAMILY_API = `http://${location.hostname}:${API_PORT}/api/family`;

const FAMILY_I18N = {
  zh: {
    section: '家庭成员',
    add_member: '+ 添加成员',
    invite_device: '+ 邀请新设备',
    primary: '主账户', current_device: '当前设备',
    devices: '设备', channels: 'IM 映射', no_devices: '暂无设备',
    th_device: '设备', th_last_used: '最近活跃', th_actions: '操作',
    th_channel: '渠道', th_external: '外部 ID',
    never: '从未使用', signed_out: '已登出', show_signed_out: '显示已登出设备',

    modal_add_member: '添加家庭成员',
    f_name: '内部名',
    f_name_hint: '英文/拼音唯一标识，如 wife / kid1',
    f_display: '显示名',
    f_display_hint: '中文/昵称，用于 UI 显示',

    modal_invite: '邀请家人添加设备',
    f_invite_owner: '为哪个成员生成邀请',
    f_invite_label: '设备用途备注（可选）',
    f_invite_label_hint: '如「老婆的 iPhone」、「客厅 iPad」— 帮助你日后识别',
    invite_link: '邀请链接',
    invite_link_hint: '把这个链接发给家人。链接 24 小时内有效，只能使用一次。',
    invite_qr_hint: '家人扫码或点链接即可登录，无需复制 token。',

    modal_add_channel: '添加 IM 映射',
    f_owner: '映射到哪个成员',
    f_channel: '渠道类型',
    f_external: '外部 ID',
    f_external_hint: 'Telegram / Discord 的 user_id 或 Withings OAuth user_id',

    activity: '操作记录',
    activity_empty: '暂无记录',
    load_more: '加载更多',
    audit_end: '— 已加载全部 —',

    btn_cancel: '取消', btn_save: '保存', btn_done: '完成', btn_copy: '复制', btn_copied: '已复制',
    btn_ok: '确定', btn_delete: '删除', btn_sign_out: '登出', btn_approve: '批准', btn_reject: '拒绝',
    confirm_title: '确认操作',
    sign_out: '登出', rename: '改名', remove: '删除', remove_account: '删除成员',

    confirm_sign_out: '让设备「{name}」立刻登出？',
    confirm_remove_account: '删除成员「{name}」？需先登出该成员的所有设备并清空其数据。',
    confirm_remove_channel: '删除映射「{channel} / {ext}」？',

    err_admin: '只有主账户能管理家庭成员',
    err_invalid: '请填写所有必填字段',
    err_current_device: '不能登出你正在使用的设备（请直接清除浏览器 cookie）',
    loading: '加载中…',

    pending_title: '等待审批的设备',
    pending_subtitle: '家人接受邀请后，需要你在这里点击批准才能登录。',
    pending_approve: '批准登录',
    pending_reject: '拒绝',
    pending_empty: '当前没有待审批设备',
    confirm_approve: '批准设备「{name}」（{owner}）登录？',
    confirm_reject_pending: '拒绝设备「{name}」？该设备将无法登录，家人需要新的邀请链接重试。',

    action_member_created: '创建了成员',
    action_member_deleted: '删除了成员',
    action_device_signed_out: '登出了设备',
    action_device_renamed: '重命名了设备',
    action_invite_created: '创建了邀请',
    action_invite_accepted: '接受了邀请',
    action_invite_revoked: '撤销了邀请',
    action_channel_added: '添加了 IM 映射',
    action_channel_removed: '删除了 IM 映射',
  },
  en: {
    section: 'Family Members',
    add_member: '+ Add member', invite_device: '+ Invite new device',
    primary: 'Admin', current_device: 'This device',
    devices: 'Devices', channels: 'IM mappings', no_devices: 'No devices yet',
    th_device: 'Device', th_last_used: 'Last active', th_actions: 'Actions',
    th_channel: 'Channel', th_external: 'External ID',
    never: 'Never used', signed_out: 'Signed out', show_signed_out: 'Show signed-out devices',

    modal_add_member: 'Add family member',
    f_name: 'Internal name', f_name_hint: 'Unique slug (wife / kid1)',
    f_display: 'Display name', f_display_hint: 'Human-readable name shown in UI',

    modal_invite: 'Invite a device',
    f_invite_owner: 'Generate invite for which member',
    f_invite_label: 'Device note (optional)',
    f_invite_label_hint: 'e.g. "Wife iPhone", "Living room iPad" — helps you recognise it later',
    invite_link: 'Invite link',
    invite_link_hint: 'Send this link to your family member. Valid for 24h, single use.',
    invite_qr_hint: 'They open the link or scan the QR — no token to copy.',

    modal_add_channel: 'Add IM mapping',
    f_owner: 'For which member',
    f_channel: 'Channel',
    f_external: 'External ID',
    f_external_hint: 'Telegram/Discord user_id or Withings OAuth user_id',

    activity: 'Activity',
    activity_empty: 'No activity yet',
    load_more: 'Load more',
    audit_end: '— end of log —',

    btn_cancel: 'Cancel', btn_save: 'Save', btn_done: 'Done', btn_copy: 'Copy', btn_copied: 'Copied',
    btn_ok: 'OK', btn_delete: 'Delete', btn_sign_out: 'Sign out', btn_approve: 'Approve', btn_reject: 'Reject',
    confirm_title: 'Confirm',
    sign_out: 'Sign out', rename: 'Rename', remove: 'Delete', remove_account: 'Remove member',

    confirm_sign_out: 'Sign out device "{name}" immediately?',
    confirm_remove_account: 'Remove member "{name}"? Their devices must be signed out and data cleared first.',
    confirm_remove_channel: 'Delete mapping "{channel} / {ext}"?',

    err_admin: 'Only the primary account can manage family',
    err_invalid: 'Please fill all required fields',
    err_current_device: "Can't sign out the device you're using (clear your browser cookie instead)",
    loading: 'Loading…',

    pending_title: 'Devices awaiting approval',
    pending_subtitle: 'After family members accept an invite, you need to approve their device here before they can sign in.',
    pending_approve: 'Approve',
    pending_reject: 'Reject',
    pending_empty: 'No pending devices',
    confirm_approve: 'Approve device "{name}" ({owner}) to sign in?',
    confirm_reject_pending: 'Reject device "{name}"? They will need a new invite to retry.',

    action_member_created: 'added member',
    action_member_deleted: 'removed member',
    action_device_signed_out: 'signed out device',
    action_device_renamed: 'renamed device',
    action_invite_created: 'created invite for',
    action_invite_accepted: 'accepted invite',
    action_invite_revoked: 'revoked invite',
    action_channel_added: 'added IM mapping',
    action_channel_removed: 'removed IM mapping',
  },
  ja: {
    section: '家族メンバー',
    add_member: '+ メンバー追加', invite_device: '+ 新しいデバイス招待',
    primary: '管理者', current_device: 'このデバイス',
    devices: 'デバイス', channels: 'IM マッピング', no_devices: 'デバイスなし',
    th_device: 'デバイス', th_last_used: '最終活動', th_actions: '操作',
    th_channel: 'チャネル', th_external: '外部 ID',
    never: '未使用', signed_out: 'ログアウト済', show_signed_out: 'ログアウト済も表示',

    modal_add_member: '家族メンバー追加',
    f_name: '内部名', f_name_hint: '一意の識別子（wife / kid1）',
    f_display: '表示名', f_display_hint: 'UI に表示される名前',

    modal_invite: 'デバイス招待',
    f_invite_owner: 'どのメンバーへの招待',
    f_invite_label: 'デバイスメモ（任意）',
    f_invite_label_hint: '例：妻の iPhone — 後で識別しやすく',
    invite_link: '招待リンク',
    invite_link_hint: '家族にこのリンクを送信。24時間有効、1回限り。',
    invite_qr_hint: '家族はリンクを開くか QR を読み取ってログイン。トークン不要。',

    modal_add_channel: 'IM マッピング追加',
    f_owner: 'どのメンバー', f_channel: 'チャネル', f_external: '外部 ID',
    f_external_hint: 'Telegram/Discord の user_id または Withings OAuth user_id',

    activity: 'アクティビティ', activity_empty: 'まだ記録なし',
    load_more: 'もっと読み込む',
    audit_end: '— すべて読み込み済 —',

    btn_cancel: 'キャンセル', btn_save: '保存', btn_done: '完了', btn_copy: 'コピー', btn_copied: 'コピー済',
    btn_ok: '確定', btn_delete: '削除', btn_sign_out: 'ログアウト', btn_approve: '承認', btn_reject: '拒否',
    confirm_title: '確認',
    sign_out: 'ログアウト', rename: '改名', remove: '削除', remove_account: 'メンバー削除',

    confirm_sign_out: 'デバイス「{name}」を即時ログアウト？',
    confirm_remove_account: 'メンバー「{name}」を削除？まずデバイスをログアウトしデータを削除する必要あり。',
    confirm_remove_channel: 'マッピング「{channel} / {ext}」を削除？',

    err_admin: 'プライマリアカウントのみ管理可能',
    err_invalid: '必須項目を入力してください',
    err_current_device: '現在使用中のデバイスはログアウト不可（ブラウザの cookie を削除してください）',
    loading: '読み込み中…',

    pending_title: '承認待ちデバイス',
    pending_subtitle: '家族が招待を受け入れた後、ここで承認するまでログインできません。',
    pending_approve: '承認', pending_reject: '拒否',
    pending_empty: '承認待ちなし',
    confirm_approve: 'デバイス「{name}」({owner}) のログインを承認？',
    confirm_reject_pending: 'デバイス「{name}」を拒否？再ログインには新しい招待が必要。',

    action_member_created: 'メンバー追加',
    action_member_deleted: 'メンバー削除',
    action_device_signed_out: 'デバイスログアウト',
    action_device_renamed: 'デバイス改名',
    action_invite_created: '招待作成',
    action_invite_accepted: '招待受諾',
    action_invite_revoked: '招待取り消し',
    action_channel_added: 'IM マッピング追加',
    action_channel_removed: 'IM マッピング削除',
  },
};

function ft(key) {
  const lang = (typeof currentLang !== 'undefined' && currentLang) || 'en';
  return (FAMILY_I18N[lang] || FAMILY_I18N.en)[key] || key;
}

function _esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

const DEVICE_ICON = {
  mobile: '📱', tablet: '📲', desktop: '💻', bot: '🤖', unknown: '❓',
};

const ACTION_LABEL = {
  'member.created': 'action_member_created',
  'member.deleted': 'action_member_deleted',
  'device.signed_out': 'action_device_signed_out',
  'device.renamed': 'action_device_renamed',
  'invite.created': 'action_invite_created',
  'invite.accepted': 'action_invite_accepted',
  'invite.revoked': 'action_invite_revoked',
  'channel.added': 'action_channel_added',
  'channel.removed': 'action_channel_removed',
};

function _timeAgo(iso) {
  if (!iso) return ft('never');
  const d = new Date(iso);
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return sec + 's';
  if (sec < 3600) return Math.floor(sec / 60) + 'm';
  if (sec < 86400) return Math.floor(sec / 3600) + 'h';
  if (sec < 86400 * 30) return Math.floor(sec / 86400) + 'd';
  return d.toLocaleDateString();
}

// ── Scoped CSS injected once ────────────────────────────────────────────

(function injectFamilyCSS() {
  if (document.getElementById('family-css')) return;
  const style = document.createElement('style');
  style.id = 'family-css';
  style.textContent = `
    #family-section .fam-grid { display: flex; flex-direction: column; gap: 12px; }
    #family-section .fam-card { background: var(--glass-card); border: 1px solid var(--card-border);
      border-radius: 10px; padding: 14px 16px; box-shadow: var(--card-shadow); }
    #family-section .fam-card-header { display: flex; align-items: center; gap: 10px; }
    #family-section .fam-card-name { font-size: 14px; font-weight: 600; color: var(--text); flex: 1; display: flex; align-items: center; gap: 8px; }
    #family-section .fam-meta { font-size: 11px; color: var(--text-faint); }
    #family-section .fam-subhead { font-size: 11px; font-weight: 600; color: var(--text-muted);
      text-transform: uppercase; letter-spacing: 0.06em; margin-top: 14px; margin-bottom: 6px;
      display: flex; align-items: center; gap: 8px; }
    #family-section .fam-subhead .fam-mini-btn { margin-left: auto; }
    #family-section .fam-device-list { display: flex; flex-direction: column; gap: 4px; }
    #family-section .fam-device-row { display: flex; align-items: center; gap: 10px;
      padding: 8px 10px; border: 1px solid var(--border-light); border-radius: 6px; background: var(--bg-hover2); }
    #family-section .fam-device-row.signed-out { opacity: 0.5; }
    #family-section .fam-device-row.current { border-color: var(--accent); background: var(--bg-accent); }
    #family-section .fam-device-icon { font-size: 22px; flex-shrink: 0; }
    #family-section .fam-device-info { flex: 1; min-width: 0; }
    #family-section .fam-device-name { font-size: 13px; font-weight: 500; color: var(--text); display: flex; align-items: center; gap: 6px; }
    #family-section .fam-device-name .rename-btn { opacity: 0; padding: 0 4px; font-size: 11px; color: var(--text-faint); cursor: pointer; background: none; border: none; }
    #family-section .fam-device-row:hover .fam-device-name .rename-btn { opacity: 1; }
    #family-section .fam-device-name .rename-btn:hover { color: var(--accent); }
    #family-section .fam-device-meta { font-size: 11px; color: var(--text-faint); margin-top: 2px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    #family-section .fam-device-actions { display: flex; gap: 6px; flex-shrink: 0; }
    #family-section .fam-btn { padding: 3px 10px; border-radius: 4px; font-size: 11px; cursor: pointer;
      border: 1px solid var(--border); background: transparent; color: var(--text-muted); }
    #family-section .fam-btn:hover { color: var(--text); border-color: var(--text-muted); }
    #family-section .fam-btn:disabled { opacity: 0.35; cursor: not-allowed; }
    #family-section .fam-btn.danger:hover { color: var(--red); border-color: var(--red); background: rgba(220,38,38,0.08); }
    #family-section .fam-mini-btn { padding: 2px 8px; font-size: 10px; }
    #family-section .badge-current { background: var(--bg-accent); color: var(--accent); }
    #family-section .badge-out { background: #3d2d2d; color: var(--text-faint); }
    body.light #family-section .badge-out { background: #f1f5f9; color: #64748b; }
    #family-section .badge-primary { background: var(--bg-accent); color: var(--accent); }

    /* Pending approval banner */
    #family-section .fam-pending-banner { background: #3a2d0a; border: 1px solid var(--yellow);
      border-radius: 10px; padding: 14px 16px; margin-bottom: 14px; }
    body.light #family-section .fam-pending-banner { background: #fef3c7; }
    #family-section .fam-pending-header { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
    #family-section .fam-pending-title { font-size: 14px; font-weight: 600; color: var(--yellow); }
    body.light #family-section .fam-pending-title { color: #92400e; }
    #family-section .fam-pending-sub { font-size: 12px; color: var(--text-2); margin-top: 2px; }
    #family-section .fam-pending-row { display: flex; align-items: center; gap: 10px;
      padding: 10px 12px; background: rgba(255,255,255,0.04); border-radius: 6px; margin-top: 6px; }
    body.light #family-section .fam-pending-row { background: rgba(0,0,0,0.04); }
    #family-section .fam-btn-approve { color: var(--green); border-color: var(--green); }
    #family-section .fam-btn-approve:hover { background: rgba(34,197,94,0.1); color: var(--green); }

    /* Channel rows (lighter than device rows) */
    #family-section .fam-tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
    #family-section .fam-tbl th { text-align: left; padding: 5px 10px; color: var(--text-faint); font-weight: 500;
      text-transform: uppercase; font-size: 10px; letter-spacing: 0.05em; border-bottom: 1px solid var(--border-light); }
    #family-section .fam-tbl td { padding: 6px 10px; border-bottom: 1px solid var(--border-light); }
    #family-section .fam-tbl tr:last-child td { border-bottom: none; }
    #family-section .fam-tbl code { background: var(--bg-hover2); padding: 1px 6px; border-radius: 3px;
      font-size: 11px; color: var(--text-2); }

    #family-section .fam-empty { padding: 14px; color: var(--text-faint); font-style: italic; font-size: 12px; text-align: center; }

    /* Activity feed */
    #family-section .fam-activity { display: flex; flex-direction: column; gap: 4px; }
    #family-section .fam-activity-row { display: flex; align-items: center; gap: 10px;
      padding: 6px 12px; font-size: 12px; color: var(--text-2); border-bottom: 1px solid var(--border-light); }
    #family-section .fam-activity-row:last-child { border-bottom: none; }
    #family-section .fam-activity-row .when { color: var(--text-faint); min-width: 80px; font-size: 11px; }
    #family-section .fam-activity-row .actor { font-weight: 500; color: var(--text); }
    #family-section .fam-activity-row .target { color: var(--accent); }

    /* Modal field layout (reuses .install-modal / .install-box) */
    .fam-form-field { margin-bottom: 14px; }
    .fam-form-field label { display: block; font-size: 11px; font-weight: 600; color: var(--text-2);
      margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
    .fam-form-field input, .fam-form-field select {
      width: 100%; background: var(--bg-input); border: 1px solid var(--border); color: var(--text);
      padding: 7px 10px; border-radius: 5px; font-size: 13px; outline: none; box-sizing: border-box;
    }
    .fam-form-field input:focus, .fam-form-field select:focus { border-color: var(--accent); }
    .fam-form-field .hint { font-size: 11px; color: var(--text-faint); margin-top: 4px; }
    .fam-form-err { color: var(--red); font-size: 12px; margin-top: 4px; min-height: 16px; }

    .fam-invite-link { font-family: monospace; background: var(--bg-input); border: 1px solid var(--accent);
      border-radius: 6px; padding: 10px 12px; font-size: 12px; word-break: break-all; color: var(--accent);
      display: flex; align-items: center; gap: 10px; margin: 8px 0; }
    .fam-invite-link code { flex: 1; }

    .fam-qr-wrap { display: flex; flex-direction: column; align-items: center; margin: 14px 0 6px; }
    .fam-qr { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
      padding: 14px; width: 180px; height: 180px; color: var(--text);
      display: flex; align-items: center; justify-content: center; }
    body.light .fam-qr { background: #fff; }
    .fam-qr svg { width: 100%; height: 100%; }

    #fam-toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
      background: var(--bg-card); border: 1px solid var(--accent); color: var(--text);
      padding: 10px 18px; border-radius: 8px; font-size: 13px; box-shadow: var(--card-shadow);
      z-index: 1000; display: none; }
    #fam-toast.err { border-color: var(--red); color: var(--red); }

    /* Custom confirm modal (replaces browser confirm()) */
    #famConfirmModal h4 { margin-bottom: 8px; }
    #famConfirmModal .install-box-btns button.fam-confirm-danger {
      background: rgba(220,38,38,0.15); border-color: var(--red); color: var(--red);
    }
    #famConfirmModal .install-box-btns button.fam-confirm-danger:hover {
      background: rgba(220,38,38,0.25);
    }
  `;
  document.head.appendChild(style);
})();

// ── Modal HTML injected once ────────────────────────────────────────────

(function injectFamilyModals() {
  if (document.getElementById('fam-modals')) return;
  const div = document.createElement('div');
  div.id = 'fam-modals';
  div.innerHTML = `
    <div class="install-modal" id="famAddMemberModal">
      <div class="install-box" style="width:480px;">
        <h4 id="famAddMemberTitle"></h4>
        <div class="fam-form-field">
          <label data-fam-label="f_name"></label>
          <input id="famAddName" type="text" autocomplete="off" />
          <div class="hint" data-fam-label="f_name_hint"></div>
        </div>
        <div class="fam-form-field">
          <label data-fam-label="f_display"></label>
          <input id="famAddDisplay" type="text" autocomplete="off" />
          <div class="hint" data-fam-label="f_display_hint"></div>
        </div>
        <div class="fam-form-err" id="famAddMemberErr"></div>
        <div class="install-box-btns">
          <button onclick="famCloseModal('famAddMemberModal')" data-fam-label="btn_cancel"></button>
          <button class="primary" onclick="famSubmitAddMember()" data-fam-label="btn_save"></button>
        </div>
      </div>
    </div>

    <div class="install-modal" id="famInviteModal">
      <div class="install-box" style="width:520px;">
        <h4 id="famInviteTitle"></h4>
        <div id="famInviteForm">
          <div class="fam-form-field">
            <label data-fam-label="f_invite_owner"></label>
            <select id="famInviteOwner"></select>
          </div>
          <div class="fam-form-field">
            <label data-fam-label="f_invite_label"></label>
            <input id="famInviteLabel" type="text" autocomplete="off" />
            <div class="hint" data-fam-label="f_invite_label_hint"></div>
          </div>
          <div class="fam-form-err" id="famInviteErr"></div>
          <div class="install-box-btns">
            <button onclick="famCloseModal('famInviteModal')" data-fam-label="btn_cancel"></button>
            <button class="primary" onclick="famSubmitInvite()" data-fam-label="btn_save"></button>
          </div>
        </div>
        <div id="famInviteResult" style="display:none;">
          <p data-fam-label="invite_link_hint" style="font-size:13px;color:var(--text-muted);"></p>
          <div class="fam-form-field">
            <label data-fam-label="invite_link"></label>
            <div class="fam-invite-link">
              <code id="famInviteUrl"></code>
              <button class="fam-btn" onclick="famCopyInviteUrl()" id="famInviteCopyBtn"></button>
            </div>
          </div>
          <div class="fam-qr-wrap" id="famQrWrap" style="display:none;">
            <div class="fam-qr" id="famQrCode"></div>
            <p data-fam-label="invite_qr_hint" style="font-size:12px;color:var(--text-faint);margin-top:6px;text-align:center;"></p>
          </div>
          <div class="install-box-btns">
            <button class="primary" onclick="famCloseModal('famInviteModal'); refreshFamily();" data-fam-label="btn_done"></button>
          </div>
        </div>
      </div>
    </div>

    <div class="install-modal" id="famAddChannelModal">
      <div class="install-box" style="width:480px;">
        <h4 id="famAddChannelTitle"></h4>
        <div class="fam-form-field">
          <label data-fam-label="f_owner"></label>
          <select id="famChanOwner"></select>
        </div>
        <div class="fam-form-field">
          <label data-fam-label="f_channel"></label>
          <select id="famChanType">
            <option value="telegram">Telegram</option>
            <option value="discord">Discord</option>
            <option value="withings">Withings</option>
          </select>
        </div>
        <div class="fam-form-field">
          <label data-fam-label="f_external"></label>
          <input id="famChanExt" type="text" autocomplete="off" />
          <div class="hint" data-fam-label="f_external_hint"></div>
        </div>
        <div class="fam-form-err" id="famAddChannelErr"></div>
        <div class="install-box-btns">
          <button onclick="famCloseModal('famAddChannelModal')" data-fam-label="btn_cancel"></button>
          <button class="primary" onclick="famSubmitAddChannel()" data-fam-label="btn_save"></button>
        </div>
      </div>
    </div>

    <div class="install-modal" id="famConfirmModal">
      <div class="install-box" style="width:420px;">
        <h4 id="famConfirmTitle"></h4>
        <p id="famConfirmMessage" style="font-size:13px;color:var(--text-2);line-height:1.6;margin:8px 0 14px;"></p>
        <div class="install-box-btns">
          <button id="famConfirmCancel" onclick="famConfirmResolve(false)"></button>
          <button id="famConfirmOk" class="primary" onclick="famConfirmResolve(true)"></button>
        </div>
      </div>
    </div>

    <div id="fam-toast"></div>
  `;
  document.body.appendChild(div);
})();

function _famApplyLabels(modalId) {
  const root = document.getElementById(modalId);
  if (!root) return;
  root.querySelectorAll('[data-fam-label]').forEach(el => {
    const key = el.getAttribute('data-fam-label');
    el.textContent = ft(key);
  });
}

function famOpenModal(modalId, titleKey) {
  const m = document.getElementById(modalId);
  if (!m) return;
  if (titleKey) {
    const h = m.querySelector('h4');
    if (h) h.textContent = ft(titleKey);
  }
  _famApplyLabels(modalId);
  m.querySelectorAll('.fam-form-err').forEach(e => e.textContent = '');
  m.classList.add('open');
}
function famCloseModal(modalId) {
  const m = document.getElementById(modalId);
  if (m) m.classList.remove('open');
}

function famToast(msg, isErr = false) {
  const t = document.getElementById('fam-toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.toggle('err', !!isErr);
  t.style.display = 'block';
  clearTimeout(famToast._t);
  famToast._t = setTimeout(() => { t.style.display = 'none'; }, 2400);
}

// ── Custom confirm modal (replaces window.confirm) ──────────────────────

let _famConfirmResolver = null;

/**
 * Promise-based replacement for window.confirm.
 * opts: { title?, message, confirmText?, cancelText?, danger? }
 * Resolves to true if user clicked confirm, false otherwise.
 */
function famConfirm(opts) {
  return new Promise(resolve => {
    _famConfirmResolver = resolve;
    document.getElementById('famConfirmTitle').textContent = opts.title || ft('confirm_title');
    document.getElementById('famConfirmMessage').textContent = opts.message || '';
    const ok = document.getElementById('famConfirmOk');
    const cancel = document.getElementById('famConfirmCancel');
    ok.textContent = opts.confirmText || ft('btn_ok');
    cancel.textContent = opts.cancelText || ft('btn_cancel');
    ok.classList.toggle('fam-confirm-danger', !!opts.danger);
    famOpenModal('famConfirmModal');
    setTimeout(() => ok.focus(), 50);
  });
}

function famConfirmResolve(answer) {
  famCloseModal('famConfirmModal');
  const r = _famConfirmResolver;
  _famConfirmResolver = null;
  if (r) r(!!answer);
}

// ESC / Enter key handlers when confirm modal is open
document.addEventListener('keydown', (e) => {
  const m = document.getElementById('famConfirmModal');
  if (!m || !m.classList.contains('open')) return;
  if (e.key === 'Escape') { e.preventDefault(); famConfirmResolve(false); }
  else if (e.key === 'Enter') { e.preventDefault(); famConfirmResolve(true); }
});

// ── Public render entry ─────────────────────────────────────────────────

function renderFamilySection() {
  return `
    <div class="section" id="family-section">
      <div class="section-title">
        ${ft('section')}
        <button class="install-btn" onclick="famOpenAddMember()">${ft('add_member')}</button>
        <button class="install-btn" onclick="famOpenInvite()" style="margin-left:6px;">${ft('invite_device')}</button>
      </div>
      <div id="family-content"><div class="loading">${ft('loading')}</div></div>
    </div>
  `;
}

// ── API plumbing ────────────────────────────────────────────────────────

async function _fapi(method, path, body) {
  const opts = {method, headers: authHeaders()};
  if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(FAMILY_API + path, opts);
  let data = null;
  try { data = await r.json(); } catch {}
  if (!r.ok) {
    const msg = (data && (data.detail || data.error)) || `HTTP ${r.status}`;
    throw new Error(msg);
  }
  return data;
}

let _famAccountsCache = [];
let _famShowSignedOut = false;

async function refreshFamily() {
  const wrap = document.getElementById('family-content');
  if (!wrap) return;
  try {
    const [accounts, devices, channels, audit, pending] = await Promise.all([
      _fapi('GET', '/accounts'),
      _fapi('GET', '/devices'),
      _fapi('GET', '/channels'),
      _fapi('GET', `/audit?limit=${AUDIT_PAGE_SIZE}&offset=0`),
      _fapi('GET', '/devices/pending'),
    ]);
    _famAccountsCache = accounts;
    const devicesByOwner = {};
    const channelsByOwner = {};
    for (const d of devices) (devicesByOwner[d.owner_id] = devicesByOwner[d.owner_id] || []).push(d);
    for (const c of channels) (channelsByOwner[c.owner_id] = channelsByOwner[c.owner_id] || []).push(c);

    const cards = accounts.map(a => _renderAccountCard(a, devicesByOwner[a.id] || [], channelsByOwner[a.id] || [])).join('');

    wrap.innerHTML = `
      ${_renderPendingBanner(pending)}
      <div style="margin-bottom:10px;font-size:11px;color:var(--text-muted);display:flex;align-items:center;gap:8px;">
        <label style="cursor:pointer;display:flex;align-items:center;gap:6px;">
          <input type="checkbox" id="famShowSignedOutToggle" ${_famShowSignedOut ? 'checked' : ''}
                 onchange="famToggleShowSignedOut(this.checked)" />
          ${ft('show_signed_out')}
        </label>
      </div>
      <div class="fam-grid">${cards}</div>
      ${_renderActivityFeed(audit)}
    `;
  } catch (e) {
    wrap.innerHTML = `<div class="empty">${ft('err_admin')}<br/><small style="color:var(--text-faint)">${_esc(e.message)}</small></div>`;
  }
}

function famToggleShowSignedOut(on) {
  _famShowSignedOut = !!on;
  refreshFamily();
}

function _renderAccountCard(a, devices, channels) {
  const isPrimary = a.id === 1;
  const visibleDevices = _famShowSignedOut ? devices : devices.filter(d => !d.revoked);
  const deviceList = visibleDevices.length
    ? `<div class="fam-device-list">${visibleDevices.map(_renderDeviceRow).join('')}</div>`
    : `<div class="fam-empty">${ft('no_devices')}</div>`;

  const channelTable = channels.length ? `
    <div class="fam-subhead">${ft('channels')}</div>
    <table class="fam-tbl">
      <thead>
        <tr>
          <th>${ft('th_channel')}</th>
          <th>${ft('th_external')}</th>
          <th>${ft('th_actions')}</th>
        </tr>
      </thead>
      <tbody>
        ${channels.map(c => `
          <tr>
            <td><span class="badge">${_esc(c.channel)}</span></td>
            <td><code>${_esc(c.external_id)}</code></td>
            <td><button class="fam-btn danger" onclick="famDeleteChannel(${c.id}, '${_esc(c.channel)}', '${_esc(c.external_id)}')">${ft('remove')}</button></td>
          </tr>
        `).join('')}
      </tbody>
    </table>` : '';

  return `
    <div class="fam-card">
      <div class="fam-card-header">
        <div class="fam-card-name">
          <span style="color:var(--text-faint);">#${a.id}</span>
          ${_esc(a.display_name || a.name)}
          <span style="color:var(--text-faint);font-weight:400;font-size:12px;">${_esc(a.name)}</span>
          ${isPrimary ? `<span class="badge badge-primary">${ft('primary')}</span>` : ''}
        </div>
        <div class="fam-meta">${a.active_devices} ${ft('devices')} · ${a.channels} ${ft('channels')}</div>
        ${isPrimary ? '' : `<button class="fam-btn danger" onclick="famDeleteAccount(${a.id}, '${_esc(a.display_name || a.name).replace(/'/g, "\\'")}')">${ft('remove_account')}</button>`}
      </div>
      <div class="fam-subhead">
        ${ft('devices')}
        <button class="install-btn fam-mini-btn" onclick="famOpenInvite(${a.id})">${ft('invite_device')}</button>
      </div>
      ${deviceList}
      ${channelTable}
      <div class="fam-subhead">${ft('channels')}<button class="install-btn fam-mini-btn" onclick="famOpenAddChannel(${a.id})">+</button></div>
      ${channels.length ? '' : `<div class="fam-empty">—</div>`}
    </div>
  `;
}

function _renderDeviceRow(d) {
  const icon = DEVICE_ICON[d.device_type] || DEVICE_ICON.unknown;
  const isCurrent = d.is_current;
  const isOut = d.revoked;
  const cls = `fam-device-row${isCurrent ? ' current' : ''}${isOut ? ' signed-out' : ''}`;
  const lastUsed = d.last_used_at ? _timeAgo(d.last_used_at) : ft('never');
  const ua = d.last_ua || '';
  const loc = [d.last_city, d.last_country].filter(Boolean).join(', ');
  const meta = [
    ua.length > 60 ? ua.slice(0, 60) + '…' : ua,
    loc ? '📍 ' + loc : null,
    lastUsed,
  ].filter(Boolean).join(' · ');

  return `
    <div class="${cls}">
      <div class="fam-device-icon">${icon}</div>
      <div class="fam-device-info">
        <div class="fam-device-name">
          ${_esc(d.device_name || 'Unnamed')}
          ${d.label ? `<span style="color:var(--text-faint);font-weight:400;font-size:12px;">(${_esc(d.label)})</span>` : ''}
          ${isCurrent ? `<span class="badge badge-current">${ft('current_device')}</span>` : ''}
          ${isOut ? `<span class="badge badge-out">${ft('signed_out')}</span>` : ''}
          <button class="rename-btn" onclick="famRenameDevice(${d.id}, '${_esc(d.device_name || '').replace(/'/g, "\\'")}')">✎</button>
        </div>
        <div class="fam-device-meta">${_esc(meta)}</div>
      </div>
      <div class="fam-device-actions">
        ${isOut ? '' : `<button class="fam-btn danger" onclick="famSignOutDevice(${d.id}, '${_esc(d.device_name || '').replace(/'/g, "\\'")}')" ${isCurrent ? 'disabled title="' + _esc(ft('err_current_device')) + '"' : ''}>${ft('sign_out')}</button>`}
      </div>
    </div>
  `;
}

function _renderPendingBanner(pending) {
  if (!pending || !pending.length) return '';
  const rows = pending.map(d => {
    const icon = DEVICE_ICON[d.device_type] || DEVICE_ICON.unknown;
    const loc = [d.last_city, d.last_country].filter(Boolean).join(', ');
    const meta = [loc ? '📍 ' + loc : null, d.last_ip || null].filter(Boolean).join(' · ');
    return `
      <div class="fam-pending-row">
        <div class="fam-device-icon">${icon}</div>
        <div class="fam-device-info">
          <div class="fam-device-name">
            ${_esc(d.device_name)}
            <span style="color:var(--text-faint);font-weight:400;font-size:12px;">
              — ${_esc(d.owner_name)} ${d.label ? `· ${_esc(d.label)}` : ''}
            </span>
          </div>
          <div class="fam-device-meta">${_esc(meta || _timeAgo(d.created_at))}</div>
        </div>
        <div class="fam-device-actions">
          <button class="fam-btn fam-btn-approve"
                  onclick="famApproveDevice(${d.id}, '${_esc(d.device_name).replace(/'/g, "\\'")}', '${_esc(d.owner_name).replace(/'/g, "\\'")}')">
            ${ft('pending_approve')}
          </button>
          <button class="fam-btn danger"
                  onclick="famRejectPending(${d.id}, '${_esc(d.device_name).replace(/'/g, "\\'")}')">
            ${ft('pending_reject')}
          </button>
        </div>
      </div>`;
  }).join('');
  return `
    <div class="fam-pending-banner">
      <div class="fam-pending-header">
        <span style="font-size:20px;">⏳</span>
        <div>
          <div class="fam-pending-title">${ft('pending_title')} (${pending.length})</div>
          <div class="fam-pending-sub">${ft('pending_subtitle')}</div>
        </div>
      </div>
      ${rows}
    </div>
  `;
}


// ── Activity feed (paginated) ───────────────────────────────────────────

const AUDIT_PAGE_SIZE = 10;
let _famAuditOffset = 0;
let _famAuditHasMore = false;

function _activityRowHtml(r) {
  const actionKey = ACTION_LABEL[r.action] || r.action;
  const actionText = ACTION_LABEL[r.action] ? ft(actionKey) : r.action;
  const targetName = r.target || (r.details && r.details.name)
                  || (r.details && r.details.device_name) || `#${r.target_id || ''}`;
  return `
    <div class="fam-activity-row">
      <span class="when">${_timeAgo(r.at)}</span>
      <span class="actor">${_esc(r.actor || '?')}</span>
      <span>${_esc(actionText)}</span>
      <span class="target">${_esc(targetName)}</span>
    </div>
  `;
}

function _renderActivityFeed(audit) {
  // `audit` is the first page response: {rows, has_more, offset, limit}
  const rows = (audit && audit.rows) || [];
  _famAuditOffset = rows.length;
  _famAuditHasMore = !!(audit && audit.has_more);
  if (!rows.length) {
    return `
      <div class="fam-subhead" style="margin-top:24px;">${ft('activity')}</div>
      <div class="fam-empty">${ft('activity_empty')}</div>`;
  }
  const rowsHtml = rows.map(_activityRowHtml).join('');
  return `
    <div class="fam-subhead" style="margin-top:24px;">${ft('activity')}</div>
    <div class="fam-card">
      <div class="fam-activity" id="fam-activity-rows">${rowsHtml}</div>
      <div id="fam-activity-more" style="text-align:center;margin-top:10px;">
        ${_famAuditHasMore
          ? `<button class="fam-btn" onclick="famLoadMoreAudit()">${ft('load_more')}</button>`
          : `<span style="color:var(--text-faint);font-size:11px;">${ft('audit_end')}</span>`}
      </div>
    </div>
  `;
}

async function famLoadMoreAudit() {
  const btn = document.querySelector('#fam-activity-more button');
  if (btn) { btn.disabled = true; btn.textContent = ft('loading'); }
  try {
    const audit = await _fapi('GET', `/audit?limit=${AUDIT_PAGE_SIZE}&offset=${_famAuditOffset}`);
    const rowsHtml = (audit.rows || []).map(_activityRowHtml).join('');
    document.getElementById('fam-activity-rows').insertAdjacentHTML('beforeend', rowsHtml);
    _famAuditOffset += (audit.rows || []).length;
    _famAuditHasMore = !!audit.has_more;
    const moreSlot = document.getElementById('fam-activity-more');
    moreSlot.innerHTML = _famAuditHasMore
      ? `<button class="fam-btn" onclick="famLoadMoreAudit()">${ft('load_more')}</button>`
      : `<span style="color:var(--text-faint);font-size:11px;">${ft('audit_end')}</span>`;
  } catch (e) {
    famToast(e.message, true);
    if (btn) { btn.disabled = false; btn.textContent = ft('load_more'); }
  }
}

function _famPopulateOwnerSelect(selectId, defaultId) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  sel.innerHTML = _famAccountsCache.map(a =>
    `<option value="${a.id}"${a.id === defaultId ? ' selected' : ''}>#${a.id} ${_esc(a.display_name || a.name)} (${_esc(a.name)})</option>`
  ).join('');
}

// ── Action handlers ─────────────────────────────────────────────────────

function famOpenAddMember() {
  document.getElementById('famAddName').value = '';
  document.getElementById('famAddDisplay').value = '';
  famOpenModal('famAddMemberModal', 'modal_add_member');
  setTimeout(() => document.getElementById('famAddName').focus(), 50);
}

async function famSubmitAddMember() {
  const name = document.getElementById('famAddName').value.trim();
  const display = document.getElementById('famAddDisplay').value.trim();
  const err = document.getElementById('famAddMemberErr');
  err.textContent = '';
  if (!name) { err.textContent = ft('err_invalid'); return; }
  try {
    await _fapi('POST', '/accounts', {name, display_name: display});
    famCloseModal('famAddMemberModal');
    famToast('✓');
    await refreshFamily();
  } catch (e) { err.textContent = e.message; }
}

async function famDeleteAccount(id, name) {
  const ok = await famConfirm({
    title: ft('remove_account'),
    message: ft('confirm_remove_account').replace('{name}', name),
    confirmText: ft('btn_delete'),
    danger: true,
  });
  if (!ok) return;
  _fapi('DELETE', `/accounts/${id}`)
    .then(() => { famToast('✓'); refreshFamily(); })
    .catch(e => famToast(e.message, true));
}

// ── Invite flow ─────────────────────────────────────────────────────────

function famOpenInvite(defaultOwnerId) {
  if (!_famAccountsCache.length) { famToast(ft('err_admin'), true); return; }
  _famPopulateOwnerSelect('famInviteOwner', defaultOwnerId);
  document.getElementById('famInviteLabel').value = '';
  document.getElementById('famInviteForm').style.display = '';
  document.getElementById('famInviteResult').style.display = 'none';
  famOpenModal('famInviteModal', 'modal_invite');
}

async function famSubmitInvite() {
  const owner_id = parseInt(document.getElementById('famInviteOwner').value, 10);
  const label = document.getElementById('famInviteLabel').value.trim();
  const err = document.getElementById('famInviteErr');
  err.textContent = '';
  try {
    const resp = await _fapi('POST', '/invites', {owner_id, label});
    // Prefer the URL the server computed (it knows the Flask port). Fall back
    // to a client-side construction if the server didn't include one.
    const url = resp.url || `${location.origin}/invite/${resp.uuid}`;
    document.getElementById('famInviteUrl').textContent = url;
    document.getElementById('famInviteCopyBtn').textContent = ft('btn_copy');

    // QR code: server returns an SVG string using `currentColor` so it adapts
    // to the page theme. If `segno` isn't installed server-side, qr_svg is
    // null — hide the QR block and only show the link.
    const qrWrap = document.getElementById('famQrWrap');
    const qrSlot = document.getElementById('famQrCode');
    if (resp.qr_svg) {
      qrSlot.innerHTML = resp.qr_svg;
      qrWrap.style.display = '';
    } else {
      qrSlot.innerHTML = '';
      qrWrap.style.display = 'none';
    }

    document.getElementById('famInviteForm').style.display = 'none';
    document.getElementById('famInviteResult').style.display = '';
    _famApplyLabels('famInviteModal');
  } catch (e) { err.textContent = e.message; }
}

function famCopyInviteUrl() {
  const url = document.getElementById('famInviteUrl').textContent;
  navigator.clipboard.writeText(url).then(() => {
    const b = document.getElementById('famInviteCopyBtn');
    b.textContent = ft('btn_copied');
    setTimeout(() => { b.textContent = ft('btn_copy'); }, 1500);
  }).catch(() => famToast('Copy failed — select & ctrl+c manually', true));
}

// ── Device actions ──────────────────────────────────────────────────────

async function famSignOutDevice(id, name) {
  const ok = await famConfirm({
    title: ft('sign_out'),
    message: ft('confirm_sign_out').replace('{name}', name || `#${id}`),
    confirmText: ft('btn_sign_out'),
    danger: true,
  });
  if (!ok) return;
  _fapi('POST', `/devices/${id}/sign-out`)
    .then(() => { famToast('✓'); refreshFamily(); })
    .catch(e => famToast(e.message, true));
}

function famRenameDevice(id, currentName) {
  const newName = prompt(ft('rename'), currentName || '');
  if (!newName || newName.trim() === currentName) return;
  _fapi('PATCH', `/devices/${id}`, {device_name: newName.trim()})
    .then(() => { famToast('✓'); refreshFamily(); })
    .catch(e => famToast(e.message, true));
}

// ── Channel actions ─────────────────────────────────────────────────────

function famOpenAddChannel(defaultOwnerId) {
  if (!_famAccountsCache.length) { famToast(ft('err_admin'), true); return; }
  _famPopulateOwnerSelect('famChanOwner', defaultOwnerId);
  document.getElementById('famChanExt').value = '';
  famOpenModal('famAddChannelModal', 'modal_add_channel');
  setTimeout(() => document.getElementById('famChanExt').focus(), 50);
}

async function famSubmitAddChannel() {
  const owner_id = parseInt(document.getElementById('famChanOwner').value, 10);
  const channel = document.getElementById('famChanType').value;
  const external_id = document.getElementById('famChanExt').value.trim();
  const err = document.getElementById('famAddChannelErr');
  err.textContent = '';
  if (!external_id) { err.textContent = ft('err_invalid'); return; }
  try {
    await _fapi('POST', '/channels', {owner_id, channel, external_id});
    famCloseModal('famAddChannelModal');
    famToast('✓');
    await refreshFamily();
  } catch (e) { err.textContent = e.message; }
}

async function famDeleteChannel(id, ch, ext) {
  const ok = await famConfirm({
    title: ft('remove'),
    message: ft('confirm_remove_channel').replace('{channel}', ch).replace('{ext}', ext),
    confirmText: ft('btn_delete'),
    danger: true,
  });
  if (!ok) return;
  _fapi('DELETE', `/channels/${id}`)
    .then(() => { famToast('✓'); refreshFamily(); })
    .catch(e => famToast(e.message, true));
}

// ── Pending device approval ─────────────────────────────────────────────

async function famApproveDevice(id, deviceName, ownerName) {
  const ok = await famConfirm({
    title: ft('pending_approve'),
    message: ft('confirm_approve').replace('{name}', deviceName).replace('{owner}', ownerName),
    confirmText: ft('btn_approve'),
  });
  if (!ok) return;
  _fapi('POST', `/devices/${id}/approve`)
    .then(() => { famToast('✓'); refreshFamily(); })
    .catch(e => famToast(e.message, true));
}

async function famRejectPending(id, deviceName) {
  const ok = await famConfirm({
    title: ft('pending_reject'),
    message: ft('confirm_reject_pending').replace('{name}', deviceName),
    confirmText: ft('btn_reject'),
    danger: true,
  });
  if (!ok) return;
  // Reject = sign out the pending device (sets revoked_at).
  _fapi('POST', `/devices/${id}/sign-out`)
    .then(() => { famToast('✓'); refreshFamily(); })
    .catch(e => famToast(e.message, true));
}
