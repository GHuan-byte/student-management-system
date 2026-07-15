// ========== 全局状态 ==========
let currentSessionId = localStorage.getItem('ai_session_id') || null;

// DOM 元素
let aiSidebar = null;
let aiOverlay = null;
let aiOpenButton = null;
let aiCloseButton = null;
let aiForm = null;
let aiInput = null;
let aiMessageList = null;
let aiSendButton = null;
let aiLoadingIndicator = null;
let aiErrorMessage = null;
let aiNewSessionButton = null;
let currentTitle = null;
let aiVoiceBtn = null;

// ========== 初始化 ==========
function cacheAiElements() {
    aiSidebar = document.getElementById('aiSidebar');
    aiOverlay = document.getElementById('aiOverlay');
    aiOpenButton = document.getElementById('aiFloatingButton');
    aiCloseButton = document.getElementById('aiCloseButton');
    aiForm = document.getElementById('aiForm');
    aiInput = document.getElementById('aiInput');
    aiMessageList = document.getElementById('aiMessageList');
    aiSendButton = document.getElementById('aiSendButton');
    aiLoadingIndicator = document.getElementById('aiLoadingIndicator');
    aiErrorMessage = document.getElementById('aiErrorMessage');
    aiNewSessionButton = document.getElementById('aiNewSessionBtn');
    currentTitle = document.getElementById('currentSessionTitle');
    aiVoiceBtn = document.getElementById('aiVoiceBtn');
}

function initAiAssistant() {
    cacheAiElements();

    if (!aiSidebar || !aiOverlay || !aiOpenButton || !aiCloseButton || !aiForm || !aiInput || !aiSendButton || !aiMessageList) {
        return;
    }

    aiInput.setAttribute('maxlength', '500');
    bindEvents();
    restoreSession();
    initSpeechRecognition();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAiAssistant, { once: true });
} else {
    initAiAssistant();
}

// ========== 事件绑定 ==========
function bindEvents() {
    if (aiOpenButton?.dataset.aiBound === 'true') return;

    aiOpenButton?.addEventListener('click', openSidebar);
    aiCloseButton?.addEventListener('click', closeSidebar);
    aiOverlay?.addEventListener('click', closeSidebar);
    aiNewSessionButton?.addEventListener('click', createNewSession);
    aiForm?.addEventListener('submit', handleSubmit);
    aiInput?.addEventListener('keydown', function(event) {
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            aiForm.requestSubmit();
        }
    });
    window.addEventListener('open-ai-assistant', openSidebar);

    aiOpenButton.dataset.aiBound = 'true';
}

// ========== 侧边栏控制 ==========
function openSidebar() {
    aiSidebar?.classList.add('open');
    aiOverlay?.classList.add('open');
    aiSidebar?.setAttribute('aria-hidden', 'false');
    aiInput?.focus();
}

function closeSidebar() {
    if (aiSidebar?.contains(document.activeElement)) {
        document.activeElement.blur();
    }
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
    return fetch('/api/sessions', {
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
            return session;
        })
        .catch(function(err) {
            console.error('创建会话失败:', err);
            throw err;
        });
}

// ========== 发送消息 ==========
async function handleSubmit(event) {
    event.preventDefault();
    if (aiSendButton?.disabled) return;

    var message = aiInput?.value.trim();
    if (!message) return;

    clearAssistantError();

    if (!currentSessionId) {
        await createNewSession();
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
            showAssistantError('抱歉，发送失败，请重试。');
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
    if (!SR) {
        aiVoiceBtn.disabled = true;
        return;
    }

    recognition = new SR();
    recognition.lang = 'zh-CN';
    recognition.continuous = false;
    recognition.interimResults = true;

    aiVoiceBtn.addEventListener('click', function() {
        if (isRecognizing) {
            recognition.stop();
            return;
        }
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
            var transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) finalText += transcript;
            else interimText += transcript;
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
function setLoading(visible) {
    aiSendButton.disabled = visible;
    aiInput.disabled = visible;
    if (aiLoadingIndicator) aiLoadingIndicator.classList.toggle('show', visible);
}

function showAssistantError(message) {
    if (aiErrorMessage) {
        aiErrorMessage.textContent = message;
        aiErrorMessage.classList.add('show');
    }
}

function clearAssistantError() {
    if (aiErrorMessage) {
        aiErrorMessage.textContent = '';
        aiErrorMessage.classList.remove('show');
    }
}

function showToast(message) {
    var toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 2600);
}

function formatTime(timestamp) {
    var date = new Date(timestamp);
    var now = new Date();
    if (now - date < 86400000 && date.getDate() === now.getDate()) {
        return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

// ========== Markdown 格式化 ==========
function escapeHtml(text) {
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatInline(text) {
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/(https?:\/\/[^\s<]+)/g, function(url) {
        return '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + '</a>';
    });
    return text;
}

function isTableSep(line) { return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line); }
function isTableRow(line) { return line.indexOf('|') !== -1; }
function splitRow(line) { return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(function(cell) { return cell.trim(); }); }

function renderTable(lines) {
    var header = splitRow(lines[0]);
    var body = lines.slice(2);
    var html = '<div class="table-wrapper"><table><thead><tr>';
    header.forEach(function(cell) { html += '<th>' + formatInline(cell) + '</th>'; });
    html += '</tr></thead><tbody>';
    body.forEach(function(line) {
        var cells = splitRow(line);
        html += '<tr>';
        cells.forEach(function(cell) { html += '<td>' + formatInline(cell) + '</td>'; });
        html += '</tr>';
    });
    return html + '</tbody></table></div>';
}

function formatBotMessage(message) {
    if (!message) return '';
    message = String(message).replace(/\r\n/g, '\n');

    var codeBlocks = [];
    message = message.replace(/```(\w+)?\n?([\s\S]*?)```/g, function(match, lang, code) {
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

        var codeMatch = line.trim().match(/^@@CODE_BLOCK_(\d+)@@$/);
        if (codeMatch) {
            var info = codeBlocks[Number(codeMatch[1])];
            var label = info.lang ? '<div class="code-lang">' + escapeHtml(info.lang) + '</div>' : '';
            result.push('<pre class="code-block">' + label + '<code>' + escapeHtml(info.code) + '</code></pre>');
            i++;
            continue;
        }

        if (i + 1 < lines.length && isTableRow(lines[i]) && isTableSep(lines[i + 1])) {
            var tableLines = [lines[i], lines[i + 1]];
            i += 2;
            while (i < lines.length && isTableRow(lines[i]) && lines[i].trim() !== '') {
                tableLines.push(lines[i]);
                i++;
            }
            result.push(renderTable(tableLines));
            continue;
        }

        if (/^###\s+/.test(line)) { result.push('<h3>' + formatInline(line.replace(/^###\s+/, '')) + '</h3>'); i++; continue; }
        if (/^##\s+/.test(line)) { result.push('<h2>' + formatInline(line.replace(/^##\s+/, '')) + '</h2>'); i++; continue; }
        if (/^#\s+/.test(line)) { result.push('<h1>' + formatInline(line.replace(/^#\s+/, '')) + '</h1>'); i++; continue; }

        if (/^\s*[-*]\s+/.test(line)) {
            var ulItems = [];
            while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
                ulItems.push('<li>' + formatInline(lines[i].replace(/^\s*[-*]\s+/, '')) + '</li>');
                i++;
            }
            result.push('<ul>' + ulItems.join('') + '</ul>');
            continue;
        }

        if (/^\s*\d+\.\s+/.test(line)) {
            var olItems = [];
            while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
                olItems.push('<li>' + formatInline(lines[i].replace(/^\s*\d+\.\s+/, '')) + '</li>');
                i++;
            }
            result.push('<ol>' + olItems.join('') + '</ol>');
            continue;
        }

        var paragraph = [];
        while (i < lines.length &&
            lines[i].trim() !== '' &&
            !/^@@CODE_BLOCK_\d+@@$/.test(lines[i].trim()) &&
            !/^#{1,3}\s+/.test(lines[i]) &&
            !/^\s*[-*]\s+/.test(lines[i]) &&
            !/^\s*\d+\.\s+/.test(lines[i]) &&
            !(i + 1 < lines.length && isTableRow(lines[i]) && isTableSep(lines[i + 1]))) {
            paragraph.push(lines[i]);
            i++;
        }
        result.push('<p>' + formatInline(paragraph.join('<br>')) + '</p>');
    }

    return result.join('');
}
