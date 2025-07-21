// Инициализация WebSocket для логов
const logSocket = new WebSocket(`ws://${window.location.host}/api/logs`);

logSocket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    if (data.type === 'log') {
        addLogEntry(data.message);
    }
};

logSocket.onerror = function(error) {
    addLogEntry('Ошибка соединения с логом', 'error');
};

logSocket.onclose = function() {
    addLogEntry('Соединение с логом закрыто', 'warning');
};

function addLogEntry(message, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;

    // Обработка сообщения
    message = message.toString().trim();
    entry.textContent = message;

    const logContent = document.getElementById('log-content');
    logContent.appendChild(entry);
    logContent.scrollTop = logContent.scrollHeight;
}


document.getElementById('clear-log').addEventListener('click', function() {
  const logContainer = document.getElementById('log-content');

  // Добавляем класс с анимацией
  logContainer.classList.add('log-flash');

  // Очищаем содержимое лога
  document.getElementById('log-content').innerHTML = '';

  // Удаляем класс после завершения анимации
  setTimeout(() => {
    logContainer.classList.remove('log-flash');
  }, 500);
});


const resizer = document.getElementById('log-resizer');
const logContainer = document.getElementById('log-container');
let isResizing = false;
let startY, startHeight;

resizer.addEventListener('mousedown', function(e) {
    isResizing = true;
    startY = e.clientY;
    startHeight = parseInt(document.defaultView.getComputedStyle(logContainer).height, 10);
    document.body.style.cursor = 'row-resize';
    e.preventDefault();
});

document.addEventListener('mousemove', function(e) {
    if (!isResizing) return;

    // Рассчитываем новую высоту относительно начальной точки
    const newHeight = startHeight + (startY - e.clientY);
    const minHeight = 40;
    const maxHeight = window.innerHeight - 150;

    logContainer.style.height = `${Math.max(minHeight, Math.min(newHeight, maxHeight))}px`;
});

document.addEventListener('mouseup', function() {
    isResizing = false;
    document.body.style.cursor = '';
});


