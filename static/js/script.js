import { GroupsManager } from './groupsManager.js';
import { VmTableManager } from './vmTableManager.js';
import { OperationsManager } from './operationsManager.js';
import { SELECTORS } from './config.js';

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация менеджера групп
    const groupsManager = new GroupsManager(SELECTORS);

    // Инициализация менеджера таблицы ВМ
    const vmTableManager = new VmTableManager(groupsManager);

    // Инициализация менеджера операций
    const operationsManager = new OperationsManager(vmTableManager);

    // Загрузка данных ВМ
    function loadVMs() {
        fetch('/api/vms')
            .then(response => response.json())
            .then(data => vmTableManager.renderVMs(data))
            .catch(error => {
                console.error('Ошибка загрузки данных:', error);
                operationsManager.showMessage('Не удалось загрузить данные о ВМ', true);
            });
    }

    // Первоначальная загрузка данных
    loadVMs();
});