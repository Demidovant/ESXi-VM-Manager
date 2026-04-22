import { SELECTORS } from './config.js';

export class GroupsManager {
    constructor(selectors = SELECTORS) {
        this.selectedGroups = [];
        this.selectors = selectors;
        this.onGroupsChanged = null; // Колбэк для оповещения об изменениях

        this.loadFromStorage();
        this.initDropdownMenu();
        this.initEventListeners();
    }

    setGroupsChangedCallback(callback) {
        this.onGroupsChanged = callback;
    }

    loadFromStorage() {
        if (localStorage.getItem('selectedGroups')) {
            try {
                this.selectedGroups = JSON.parse(localStorage.getItem('selectedGroups'));
                this.selectedGroups.forEach(group => {
                    const checkbox = document.querySelector(`.group-checkbox[value="${group}"]`);
                    if (checkbox) checkbox.checked = true;
                });
                this.updateSelectedCount();
            } catch (e) {
                console.error('Ошибка восстановления групп:', e);
                localStorage.removeItem('selectedGroups');
            }
        }
    }

    initDropdownMenu() {
        this.groupFilterDisplay = document.getElementById('group-filter-display');
        this.checkboxes = document.getElementById('checkboxes');
        this.overSelect = document.querySelector('.over-select');

        this.clickInsideMenu = false;

        this.overSelect?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.checkboxes.style.display = this.checkboxes.style.display === 'block' ? 'none' : 'block';
        });

        this.checkboxes?.addEventListener('click', () => {
            this.clickInsideMenu = true;
        });

        document.addEventListener('click', () => {
            if (!this.clickInsideMenu && !this.overSelect?.contains(event.target)) {
                this.checkboxes.style.display = 'none';
            }
            this.clickInsideMenu = false;
        });
    }

    initEventListeners() {
        document.querySelector(this.selectors.clearGroupsBtn)?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.clearGroups();
        });

        document.querySelectorAll('.group-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                e.stopPropagation();
                const group = e.target.value;
                if (e.target.checked) {
                    if (!this.selectedGroups.includes(group)) {
                        this.selectedGroups.push(group);
                    }
                } else {
                    this.selectedGroups = this.selectedGroups.filter(g => g !== group);
                }
                this.updateSelectedCount();
                this.notifyGroupsChanged();
            });
        });
    }

    clearGroups() {
        document.querySelectorAll('.group-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        this.selectedGroups = [];
        this.updateSelectedCount();
        this.notifyGroupsChanged();
    }

    notifyGroupsChanged() {
        if (this.onGroupsChanged) {
            this.onGroupsChanged(this.selectedGroups);
        }
    }

    updateSelectedCount() {
        const count = this.selectedGroups.length;
        const placeholder = document.querySelector(this.selectors.groupsPlaceholder);
        if (placeholder) {
            placeholder.textContent = count > 0 ? `${count} выбрано` : 'Выберите группы';
        }
        localStorage.setItem('selectedGroups', JSON.stringify(this.selectedGroups));
    }

    getSelectedGroups() {
        return this.selectedGroups;
    }

    updateGroupsList(groups) {
        const container = document.querySelector('.checkboxes-list');
        if (!container) return;

        // Очищаем контейнер
        container.innerHTML = '';

        // Создаём чекбоксы для каждой группы
        groups.forEach(group => {
            const label = document.createElement('label');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'group-checkbox';
            checkbox.value = group;

            const span = document.createElement('span');
            span.textContent = group;

            label.appendChild(checkbox);
            label.appendChild(span);
            container.appendChild(label);
        });

        // Сбрасываем выбранные группы
        this.selectedGroups = [];
        localStorage.removeItem('selectedGroups'); // очищаем сохранённое состояние
        this.updateSelectedCount();

        // Переинициализируем обработчики событий для новых чекбоксов
        this.initEventListeners();

        // Оповещаем об изменении (чтобы таблица перерисовалась)
        this.notifyGroupsChanged();
    }

    setSelectedGroups(groups) {
        this.selectedGroups = groups;
        // Обновляем чекбоксы в DOM
        document.querySelectorAll('.group-checkbox').forEach(checkbox => {
            checkbox.checked = groups.includes(checkbox.value);
        });
        this.updateSelectedCount();
        this.notifyGroupsChanged();
    }

}