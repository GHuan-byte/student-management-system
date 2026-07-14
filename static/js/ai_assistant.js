// ========== 全局状态 ==========
let currentSessionId = localStorage.getItem('ai_session_id') || null;

// DOM 元素
const aiSidebar = document.getElementById('aiSidebar');
const aiOverlay = document.getElementById('aiOverlay');
const aiOpenButton = document.getElementById('aiFloatingButton');
const aiCloseButton = document.getElementById('aiCloseButton');
const aiForm = document.getElementById('aiAssistantForm');
const aiInput = document.getElementById('aiAssistantInput');
const aiMessageList = document.getElementById('aiMessageList');
const aiSendButton = document.getElementById('aiSendButton');
const aiLoadingIndicator = document.getElementById('aiLoadingIndicator');
const aiErrorMessage = document.getElementById('aiErrorMessage');
const aiNewSessionButton = document.getElementById('aiNewSessionBtn');
const currentTitle = document.getElementById('currentSessionTitle');
const aiVoiceBtn = document.getElementById('aiVoiceBtn');
const aiStudentsOpenButton = document.getElementById('openAssistantOnStudents');

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', function() {
    if (aiInput) aiInput.setAttribute('maxlength', '1000');
    bindEvents();
    restoreSession();
    initSpeechRecognition();
});

// ========== 事件绑定 ==========
function bindEvents() {
    aiOpenButton?.addEventListener('click', openSidebar);
    aiStudentsOpenButton?.addEventListener('click', openSidebar);
    aiCloseButton?.addEventListener('click', closeSidebar);
    aiOverlay?.addEventListener('click', closeSidebar);
    aiNewSessionButton?.addEventListener('click', createNewSession);
    aiForm?.addEventListener('submit', handleSubmit);
    aiInput?.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            aiForm.requestSubmit();
        }
    });
    window.addEventListener('open-ai-assistant', openSidebar);
}

// ========== 侧边栏控制 ==========
function openSidebar() {
    aiSidebar?.classList.add('open');
    aiOverlay?.classList.add('open');
    aiSidebar?.setAttribute('aria-hidden', 'false');
    aiInput?.focus();
}

function closeSidebar() {
    aiSidebar?.classList.remove('open');
    aiOverlay?.classList.remove('open');
    aiSidebar?.setAttribute('aria-hidden', 'true');
}

// ========== 会话恢复 ==========
function restoreSession() {
    if (!currentSessionId) return;
    fetch('/api/sessions/' + currentSessionId + '/messages?limit=100')
        .then(function(res) {
            if (!res.ok) throw new Error('session not found');
            return res.json();
        })
        .then(function(messages) {
            if (messages.length) {
                aiMessageList.innerHTML = '';
                messages.forEach(function(msg) {
                    appendMessage(msg.message, msg.sender === 'user' ? 'user' : 'assistant', msg.timestamp);
                });
            }
        })
        .catch(function() {
            localStorage.removeItem('ai_session_id');
            currentSessionId = null;
        });
}

function createNewSession() {
    fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: '新对话' })
    })
    .then(function(res) { return res.json(); })
    .then(function(session) {
        currentSessionId = session.id;
        localStorage.setItem('ai_session_id', currentSessionId);
        aiMessageList.innerHTML =
            '<div class="ai-message ai-message-assistant"><div class="ai-message-bubble">新对话，开始聊天吧！</div></div>';
        if (currentTitle) currentTitle.textContent = '💬 ' + session.title;
    })
    .catch(function(err) { console.error('创建会话失败:', err); });
}

// ========== 发送消息 ==========
function handleSubmit(e) {
    e.preventDefault();
    if (aiSendButton?.disabled) return;
    var message = aiInput?.value.trim();
    if (!message) return;

    clearAssistantError();

    if (!currentSessionId) {
        createNewSession();
        setTimeout(function() { sendMessage(message); }, 300);
        aiInput.value = '';
        return;
    }

    appendMessage(message, 'user');
    aiInput.value = '';
    sendMessage(message);
}

function sendMessage(message) {
    aiSendButton.disabled = true;
    aiSendButton.textContent = '发送中...';
    setLoading(true);

    var typingIndicator = addTypingIndicator();

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, session_id: currentSessionId })
    })
    .then(function(response) {
        if (!response.ok) throw new Error('服务器响应失败');
        return response.json();
    })
    .then(function(data) {
        typingIndicator.remove();
        if (data.session_id && data.session_id !== currentSessionId) {
            currentSessionId = data.session_id;
            localStorage.setItem('ai_session_id', currentSessionId);
        }
        appendMessage(data.bot_reply, 'assistant');
    })
    .catch(function(error) {
        typingIndicator.remove();
        console.error(error);
        showToast('抱歉，发送失败，请重试。');
    })
    .finally(function() {
        aiSendButton.disabled = false;
        aiSendButton.textContent = '发送';
        setLoading(false);
        aiInput?.focus();
    });
}

// ========== 消息渲染 ==========
function appendMessage(message, sender, timestamp) {
    var wrapper = document.createElement('div');
    wrapper.className = 'ai-message ai-message-' + sender;

    var bubble = document.createElement('div');
    bubble.className = 'ai-message-bubble';

    if (sender === 'assistant') {
        bubble.innerHTML = formatBotMessage(message);
        var copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.type = 'button';
        copyBtn.textContent = '复制';
        copyBtn.title = '复制这条消息';
        copyBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            copyMessageText(message, copyBtn);
        });
        bubble.appendChild(copyBtn);
    } else {
        bubble.textContent = message;
    }

    var timeSpan = document.createElement('span');
    timeSpan.className = 'message-time';
    timeSpan.textContent = formatTime(timestamp || new Date());
    bubble.appendChild(timeSpan);

    wrapper.appendChild(bubble);
    aiMessageList.appendChild(wrapper);
    aiMessageList.scrollTop = aiMessageList.scrollHeight;
}

function addTypingIndicator() {
    var div = document.createElement('div');
    div.className = 'ai-message ai-message-assistant typing-indicator';
    div.innerHTML = '<div class="ai-message-bubble"><p>正在输入<span class="dots">...</span></p></div>';
    aiMessageList.appendChild(div);
    aiMessageList.scrollTop = aiMessageList.scrollHeight;
    return div;
}

// ========== 复制消息 ==========
async function copyMessageText(text, button) {
    try {
        await navigator.clipboard.writeText(text);
        button.textContent = '已复制';
        showToast('消息已复制');
        setTimeout(function() { button.textContent = '复制'; }, 1000);
    } catch (error) {
        var textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            button.textContent = '已复制';
            showToast('消息已复制');
            setTimeout(function() { button.textContent = '复制'; }, 1000);
        } catch (e) {
            showToast('复制失败');
        }
        document.body.removeChild(textarea);
    }
}

// ========== 语音输入 ==========
var recognition = null;
var isRecognizing = false;
var baseTranscript = '';

function initSpeechRecognition() {
    if (!aiVoiceBtn || !aiInput) return;
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { aiVoiceBtn.disabled = true; return; }

    recognition = new SR();
    recognition.lang = 'zh-CN';
    recognition.continuous = false;
    recognition.interimResults = true;

    aiVoiceBtn.addEventListener('click', function() {
        if (isRecognizing) { recognition.stop(); return; }
        baseTranscript = aiInput.value.trim();
        recognition.start();
    });

    recognition.onstart = function() {
        isRecognizing = true;
        aiVoiceBtn.classList.add('listening');
        aiVoiceBtn.textContent = '🔴';
    };

    recognition.onresult = function(event) {
        var finalText = '';
        var interimText = '';
        for (var i = event.resultIndex; i < event.results.length; i++) {
            var t = event.results[i][0].transcript;
            if (event.results[i].isFinal) finalText += t;
            else interimText += t;
        }
        if (finalText) baseTranscript = (baseTranscript + ' ' + finalText).trim();
        aiInput.value = (baseTranscript + ' ' + interimText).trim();
    };

    recognition.onerror = function() { showToast('语音识别失败'); };
    recognition.onend = function() {
        isRecognizing = false;
        aiVoiceBtn.classList.remove('listening');
        aiVoiceBtn.textContent = '🎤';
    };
}

// ========== 工具函数 ==========
function setLoading(v) {
    aiSendButton.disabled = v;
    aiInput.disabled = v;
    if (aiLoadingIndicator) aiLoadingIndicator.classList.toggle('show', v);
}

function showAssistantError(msg) {
    if (aiErrorMessage) { aiErrorMessage.textContent = msg; aiErrorMessage.classList.add('show'); }
}

function clearAssistantError() {
    if (aiErrorMessage) { aiErrorMessage.textContent = ''; aiErrorMessage.classList.remove('show'); }
}

function showToast(msg) {
    var t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function() { t.remove(); }, 2600);
}

function formatTime(ts) {
    var d = new Date(ts);
    var n = new Date();
    if (n - d < 86400000 && d.getDate() === n.getDate())
        return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

// ========== Markdown 格式化 ==========
function escapeHtml(text) {
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatInline(text) {
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/(https?:\/\/[^\s<]+)/g, function(u) {
        return '<a href="' + u + '" target="_blank" rel="noopener noreferrer">' + u + '</a>';
    });
    return text;
}

function isTableSep(l) { return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(l); }
function isTableRow(l) { return l.indexOf('|') !== -1; }
function splitRow(l) { return l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(function(c) { return c.trim(); }); }

function renderTable(lines) {
    var h = splitRow(lines[0]);
    var b = lines.slice(2);
    var html = '<div class="table-wrapper"><table><thead><tr>';
    h.forEach(function(c) { html += '<th>' + formatInline(c) + '</th>'; });
    html += '</tr></thead><tbody>';
    b.forEach(function(line) {
        var cells = splitRow(line);
        html += '<tr>';
        cells.forEach(function(c) { html += '<td>' + formatInline(c) + '</td>'; });
        html += '</tr>';
    });
    return html + '</tbody></table></div>';
}

function formatBotMessage(message) {
    if (!message) return '';
    message = String(message).replace(/\r\n/g, '\n');

    var codeBlocks = [];
    message = message.replace(/```(\w+)?\n?([\s\S]*?)```/g, function(m, lang, code) {
        var idx = codeBlocks.length;
        codeBlocks.push({ lang: lang || '', code: code });
        return '\n@@CODE_BLOCK_' + idx + '@@\n';
    });

    message = escapeHtml(message);
    var lines = message.split('\n');
    var result = [];
    var i = 0;

    while (i < lines.length) {
        var line = lines[i];
        if (line.trim() === '') { i++; continue; }

        var cm = line.trim().match(/^@@CODE_BLOCK_(\d+)@@$/);
        if (cm) {
            var info = codeBlocks[Number(cm[1])];
            var label = info.lang ? '<div class="code-lang">' + escapeHtml(info.lang) + '</div>' : '';
            result.push('<pre class="code-block">' + label + '<code>' + escapeHtml(info.code) + '</code></pre>');
            i++; continue;
        }

        if (i + 1 < lines.length && isTableRow(lines[i]) && isTableSep(lines[i + 1])) {
            var tbl = [lines[i], lines[i + 1]]; i += 2;
            while (i < lines.length && isTableRow(lines[i]) && lines[i].trim() !== '') { tbl.push(lines[i]); i++; }
            result.push(renderTable(tbl)); continue;
        }

        if (/^###\s+/.test(line)) { result.push('<h3>' + formatInline(line.replace(/^###\s+/, '')) + '</h3>'); i++; continue; }
        if (/^##\s+/.test(line)) { result.push('<h2>' + formatInline(line.replace(/^##\s+/, '')) + '</h2>'); i++; continue; }
        if (/^#\s+/.test(line)) { result.push('<h1>' + formatInline(line.replace(/^#\s+/, '')) + '</h1>'); i++; continue; }

        if (/^\s*[-*]\s+/.test(line)) {
            var items = [];
            while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
                items.push('<li>' + formatInline(lines[i].replace(/^\s*[-*]\s+/, '')) + '</li>'); i++;
            }
            result.push('<ul>' + items.join('') + '</ul>'); continue;
        }

        if (/^\s*\d+\.\s+/.test(line)) {
            var items = [];
            while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
                items.push('<li>' + formatInline(lines[i].replace(/^\s*\d+\.\s+/, '')) + '</li>'); i++;
            }
            result.push('<ol>' + items.join('') + '</ol>'); continue;
        }

        var para = [];
        while (i < lines.length && lines[i].trim() !== '' &&
            !/^@@CODE_BLOCK_\d+@@$/.test(lines[i].trim()) &&
            !/^#{1,3}\s+/.test(lines[i]) &&
            !/^\s*[-*]\s+/.test(lines[i]) &&
            !/^\s*\d+\.\s+/.test(lines[i]) &&
            !(i + 1 < lines.length && isTableRow(lines[i]) && isTableSep(lines[i + 1]))) {
            para.push(lines[i]); i++;
        }
        result.push('<p>' + formatInline(para.join('<br>')) + '</p>');
    }
    return result.join('');
}
