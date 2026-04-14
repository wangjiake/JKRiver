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
