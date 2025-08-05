import { SELECTORS } from './config.js';

export class OperationsManager {
    constructor(vmTableManager) {
        this.vmTableManager = vmTableManager;
        this.abortController = null;
        this.currentOperation = null;
        this.initEventListeners();
        this.setupOperationUpdates();
    }

    resetOperationStatus() {
        document.querySelectorAll(SELECTORS.operationCheckbox).forEach(checkbox => {
            checkbox.classList.remove(
                SELECTORS.operationSuccess,
                SELECTORS.operationError,
                SELECTORS.operationActive
            );
        });
    }

    updateOperationStatus(vmName, operation, status) {
        const checkbox = document.querySelector(
            `tr[data-vm="${vmName}"] .operation-checkbox[data-operation="${operation}"]`
        );

        if (checkbox) {
            checkbox.classList.remove(
                SELECTORS.operationSuccess,
                SELECTORS.operationError,
                SELECTORS.operationActive
            );

            if (status === 'success') {
                checkbox.classList.add(SELECTORS.operationSuccess);
            } else if (status === 'error') {
                checkbox.classList.add(SELECTORS.operationError);
            } else if (status === 'active') {
                checkbox.classList.add(SELECTORS.operationActive);
            }
        }
    }

    initEventListeners() {
        document.querySelector(SELECTORS.executeBtn).addEventListener('click', () => this.executeOperations());
        document.querySelector(SELECTORS.cancelBtn).addEventListener('click', () => this.cancelOperations());
        document.querySelector(SELECTORS.clearFilterBtn).addEventListener('click', () => this.clearSelection());

        // Сброс статусов при изменении чекбоксов
        document.addEventListener('change', (e) => {
            if (e.target.matches(SELECTORS.operationCheckbox)) {
                this.resetOperationStatus();
            }
        });

        // Сброс статусов при очистке таблицы
        document.querySelector(SELECTORS.clearFilterBtn).addEventListener('click', () => {
            this.resetOperationStatus();
        });
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
        this.resetOperationStatus();

        // Проверка имени снапшота
        if (Array.from(allOperations).includes('snapshot')) {
            const snapshotNameInput = document.querySelector(SELECTORS.snapshotNameInput);
            const snapshotName = snapshotNameInput.value.trim();

            if (snapshotName && !/^[a-zA-Z0-9_-]+$/.test(snapshotName)) {
                this.showMessage('Имя снапшота должно содержать только латинские буквы, цифры, дефисы и подчеркивания', true);
                return;
            }

            vmOperations.forEach(vm => {
                if (vm.operations.includes('snapshot')) {
                    vm.snapshot_name = snapshotName;
                }
            });
        }

        // Проверка имени снапшота для отката
        if (Array.from(allOperations).includes('revert')) {
            const revertNameInput = document.querySelector(SELECTORS.revertNameInput);
            const revertName = revertNameInput.value.trim();

            if (!revertName) {
                this.showMessage('Для отката необходимо указать имя снапшота', true);
                return;
            }

            if (!/^[a-zA-Z0-9_-]+$/.test(revertName)) {
                this.showMessage('Имя снапшота должно содержать только латинские буквы, цифры, дефисы и подчеркивания', true);
                return;
            }

            vmOperations.forEach(vm => {
                if (vm.operations.includes('revert')) {
                    vm.revert_name = revertName;
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

        let sessionId = null;

        try {
            // 1. Начинаем сессию операций
            const startResponse = await fetch('/api/start-operations', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ vmOperations }),
                signal: this.abortController.signal
            });

            if (!startResponse.ok) throw new Error('Ошибка начала операций');

            const startData = await startResponse.json();
            sessionId = startData.session_id;

            // 2. Выполняем операции последовательно
            for (const vm of vmOperations) {
                if (this.abortController.signal.aborted) break;

                for (const op of vm.operations) {
                    if (this.abortController.signal.aborted) break;

                    // Подсвечиваем текущую операцию
                    this.updateOperationStatus(vm.vm, op, 'active');
                    this.currentOperation = { vmName: vm.vm, operation: op };

                    try {
                        const opResponse = await fetch('/api/execute-operation', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                session_id: sessionId,
                                vm_name: vm.vm,
                                operation: op,
                                snapshot_name: vm.snapshot_name,
                                revert_name: vm.revert_name
                            }),
                            signal: this.abortController.signal
                        });

                    const opData = await opResponse.json();

                    // Правильно определяем статус операции
                    const opStatus = opData.status === "error" ? 'error' : 'success';
                    this.updateOperationStatus(vm.vm, op, opStatus);

                    if (opData.status === "critical_error") {
                        throw new Error(opData.message);
                    }

                    if (opStatus === 'error') {
                        console.error(opData.message);
                    }

                } catch (error) {
                    this.updateOperationStatus(vm.vm, op, 'error');

                    if (error.message.toLowerCase().includes("подключ") ||
                        error.message.toLowerCase().includes("connect")) {
                        throw error;
                    }

                    console.error(error.message);
                    continue;

                    } finally {
                        this.currentOperation = null;
                    }
                }
            }

            // 3. Завершаем сессию и получаем итоговый отчет
            const finishResponse = await fetch('/api/finish-operations', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ session_id: sessionId })
            });

            if (!finishResponse.ok) throw new Error('Ошибка завершения операций');

            const finishData = await finishResponse.json();
            let message = finishData.message;
            // if (finishData.errors?.length > 0) {
            //     message += ` (ошибок: ${finishData.errors.length})`;
            // }
            this.showMessage(message, finishData.status === "error");

        } catch (error) {
            if (sessionId) {
                // При ошибке отменяем сессию
                await fetch('/api/cancel-operations', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ session_id: sessionId })
                });
            }

            if (error.name === 'AbortError') {
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
            this.currentOperation = null;
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

    setupOperationUpdates() {
        const eventSource = new EventSource('/api/operation-updates');
        eventSource.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.operation && data.status) {
                const [vmName, opName] = data.operation.split('_');
                this.updateOperationStatus(vmName, opName, data.status);
            }
        };
    }

}