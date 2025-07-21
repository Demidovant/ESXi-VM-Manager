import {COLUMN_COUNT, OPERATIONS, SELECTORS} from './config.js';

export class VmTableManager {
    constructor(groupsManager) {
        this.groupsManager = groupsManager;
        this.vms = [];

        // Подписываемся на изменения групп
        this.groupsManager.setGroupsChangedCallback(() => {
            if (this.vms.length > 0) {
                this.renderVMs(this.vms);
            }
        });
    }

    renderVMs(vms) {
        this.vms = vms; // Сохраняем VMs для повторного использования

        const filteredVMs = this.groupsManager.getSelectedGroups().length === 0
            ? vms
            : vms.filter(vm => this.groupsManager.getSelectedGroups().includes(vm.GROUP_NAME));

        const groups = [...new Set(filteredVMs.map(vm => vm.GROUP_NAME))];
        let html = '';

        groups.forEach(group => {
            html += `<tr class="group-header"><td colspan="${COLUMN_COUNT}">${group}</td></tr>`;

            filteredVMs
                .filter(vm => vm.GROUP_NAME === group)
                .forEach(vm => {
                    html += `
                    <tr data-vm="${vm.TARGET_VM_NAME}">
                        <td></td>
                        <td>${vm.TARGET_VM_NAME}</td>
                        ${OPERATIONS.map(op => 
                            `<td><input type="checkbox" class="operation-checkbox" data-operation="${op}"></td>`
                        ).join('')}
                    </tr>`;
                });
        });

        document.querySelector(SELECTORS.vmTableBody).innerHTML = html;
        this.initSelectAllHandlers();
    }


    initSelectAllHandlers() {
        OPERATIONS.forEach(operation => {
            const headerCheckbox = document.getElementById(`select-all-${operation}`);
            if (headerCheckbox) {
                headerCheckbox.addEventListener('change', function() {
                    const isChecked = this.checked;
                    document.querySelectorAll(`.operation-checkbox[data-operation="${operation}"]`).forEach(cb => {
                        cb.checked = isChecked;
                    });
                    this.indeterminate = false;
                });

                document.querySelectorAll(`.operation-checkbox[data-operation="${operation}"]`).forEach(checkbox => {
                    checkbox.addEventListener('change', () => {
                        this.updateHeaderCheckboxState(operation);
                    });
                });

                this.updateHeaderCheckboxState(operation);
            }
        });
    }

    updateHeaderCheckboxState(operation) {
        const headerCheckbox = document.getElementById(`select-all-${operation}`);
        if (!headerCheckbox) return;

        const visibleCheckboxes = document.querySelectorAll(
            `.operation-checkbox[data-operation="${operation}"]:not([style*="display: none"])`
        );

        if (visibleCheckboxes.length === 0) {
            headerCheckbox.checked = false;
            headerCheckbox.indeterminate = false;
            return;
        }

        const checkedCount = Array.from(visibleCheckboxes).filter(cb => cb.checked).length;

        if (checkedCount === 0) {
            headerCheckbox.checked = false;
            headerCheckbox.indeterminate = false;
        } else if (checkedCount === visibleCheckboxes.length) {
            headerCheckbox.checked = true;
            headerCheckbox.indeterminate = false;
        } else {
            headerCheckbox.checked = false;
            headerCheckbox.indeterminate = true;
        }
    }

    clearSelection() {
        document.querySelectorAll('.operation-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        OPERATIONS.forEach(op => {
            const headerCheckbox = document.getElementById(`select-all-${op}`);
            if (headerCheckbox) {
                headerCheckbox.checked = false;
                headerCheckbox.indeterminate = false;
            }
        });
    }

    getSelectedOperations() {
        const vmOperations = [];
        const allOperations = new Set();

        document.querySelectorAll('tr[data-vm]').forEach(row => {
            const vmName = row.dataset.vm;
            const operations = [];

            row.querySelectorAll('.operation-checkbox').forEach(checkbox => {
                if (checkbox.checked) {
                    const operation = checkbox.dataset.operation;
                    operations.push(operation);
                    allOperations.add(operation);
                }
            });

            if (operations.length > 0) {
                vmOperations.push({
                    vm: vmName,
                    operations: operations
                });
            }
        });

        return { vmOperations, allOperations };
    }
}