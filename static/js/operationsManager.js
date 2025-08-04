import { SELECTORS } from './config.js';

export class OperationsManager {
    constructor(vmTableManager) {
        this.vmTableManager = vmTableManager;
        this.abortController = null;
        this.initEventListeners();
    }

    initEventListeners() {
        document.querySelector(SELECTORS.executeBtn).addEventListener('click', () => this.executeOperations());
        document.querySelector(SELECTORS.cancelBtn).addEventListener('click', () => this.cancelOperations());
        document.querySelector(SELECTORS.clearFilterBtn).addEventListener('click', () => this.clearSelection());
    }

    lockCheckboxes() {
        // Блокируем все чекбоксы операций и заголовков
        document.querySelectorAll('.operation-checkbox, .header-checkbox').forEach(checkbox => {
            checkbox.disabled = true;
        });

        // Блокируем чекбоксы групп
        document.querySelectorAll(SELECTORS.groupCheckboxes).forEach(checkbox => {
            checkbox.disabled = true;
        });

        // Блокируем кнопку очистки групп
        const clearBtn = document.querySelector(SELECTORS.clearGroupsBtn);
        if (clearBtn) {
            clearBtn.disabled = true;
        }

        // Блокируем элемент открытия меню групп
        const groupSelect = document.querySelector(SELECTORS.selectBox);
        if (groupSelect) {
            groupSelect.style.pointerEvents = 'none';
            groupSelect.style.opacity = '0.5';
            groupSelect.style.cursor = 'not-allowed';
        }
    }

    unlockCheckboxes() {
        // Разблокируем все чекбоксы операций и заголовков
        document.querySelectorAll('.operation-checkbox, .header-checkbox').forEach(checkbox => {
            checkbox.disabled = false;
        });

        // Разблокируем чекбоксы групп
        document.querySelectorAll(SELECTORS.groupCheckboxes).forEach(checkbox => {
            checkbox.disabled = false;
        });

        // Разблокируем кнопку очистки групп
        const clearBtn = document.querySelector(SELECTORS.clearGroupsBtn);
        if (clearBtn) {
            clearBtn.disabled = false;
        }

        // Разблокируем элемент открытия меню групп
        const groupSelect = document.querySelector(SELECTORS.selectBox);
        if (groupSelect) {
            groupSelect.style.pointerEvents = 'auto';
            groupSelect.style.opacity = '1';
            groupSelect.style.cursor = 'pointer';
        }
    }

    async executeOperations() {
        const { vmOperations, allOperations } = this.vmTableManager.getSelectedOperations();

            // Проверка имени снапшота, если есть операции снапшота
        if (Array.from(allOperations).includes('snapshot')) {
            const snapshotNameInput = document.querySelector(SELECTORS.snapshotNameInput);
            const snapshotName = snapshotNameInput.value.trim();

            if (snapshotName && !/^[a-zA-Z0-9_-]+$/.test(snapshotName)) {
                this.showMessage('Имя снапшота должно содержать только латинские буквы, цифры, дефисы и подчеркивания', true);
                return;
            }

            // Добавляем имя снапшота в данные операций
            vmOperations.forEach(vm => {
                if (vm.operations.includes('snapshot')) {
                    vm.snapshot_name = snapshotName;
                }
            });
        }

        if (vmOperations.length === 0) {
            this.showMessage('Не выбрано ни одной ВМ для операций', true);
            return;
        }

        if (allOperations.size === 0) {
            this.showMessage('Не выбрано ни одной операции', true);
            return;
        }

        if (Array.from(allOperations).includes('delete') &&
            prompt('Для подтверждения удаления введите слово "delete":')?.toLowerCase() !== 'delete') {
            this.showMessage('Операция удаления отменена', true);
            return;
        }

        const executeBtn = document.querySelector(SELECTORS.executeBtn);
        const cancelBtn = document.querySelector(SELECTORS.cancelBtn);
        const clearFilterBtn = document.querySelector(SELECTORS.clearFilterBtn);
        const selectBox = document.querySelector(SELECTORS.selectBox);

        executeBtn.disabled = true;
        clearFilterBtn.disabled = true;
        selectBox.disabled = true;
        cancelBtn.disabled = false;
        this.abortController = new AbortController();

        // Блокируем чекбоксы перед началом операций
        this.lockCheckboxes();

        try {
            const response = await fetch('/api/execute', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ vmOperations }),
                signal: this.abortController.signal
            });

            if (!response.ok) throw new Error('Ошибка сервера');

            const data = await response.json();
            let message = `${data.message}\nУспешно: ${data.success_count}/${data.total_operations}`;
            if (data.errors?.length > 0) {
                message += `\nОшибки: ${data.errors.length}`;
            }
            this.showMessage(message, data.status === "error");

        } catch (error) {
            if (error.name === 'AbortError') {
                await fetch('/api/cancel', { method: 'POST' });
                this.showMessage('Выполнение операций прервано', true);
            } else {
                console.error('Ошибка:', error);
                this.showMessage(`Ошибка: ${error.message || error}`, true);
            }
        } finally {
            executeBtn.disabled = false;
            clearFilterBtn.disabled = false;
            selectBox.disabled = false;
            cancelBtn.disabled = true;
            this.abortController = null;

            // Разблокируем чекбоксы после завершения операций
            this.unlockCheckboxes();
        }
    }

    cancelOperations() {
        if (this.abortController) {
            this.abortController.abort();
            this.showMessage('Запрос на прерывание отправлен...', false);
            this.unlockCheckboxes();
        }
    }

    clearSelection() {
        this.vmTableManager.clearSelection();
        this.showMessage('Все выделения в таблице очищены');
        this.unlockCheckboxes();
    }

    showMessage(text, isError = false) {
        const container = document.querySelector(SELECTORS.messageContainer);
        const message = document.createElement('div');
        message.className = `message ${isError ? 'error' : 'success'}`;
        message.textContent = text;
        container.appendChild(message);

        setTimeout(() => {
            message.style.animation = 'fadeOut 0.5s forwards';
            message.addEventListener('animationend', () => message.remove());
        }, 5000);
    }
}