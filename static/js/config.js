// Константы для операций
export const OPERATIONS = ['delete', 'clone', 'customize', 'hardware', 'snapshot', 'revert', 'poweroff', 'poweron'];
export const COLUMN_COUNT = OPERATIONS.length + 2; // +2 для group-col и vm-col

// Селекторы элементов
export const SELECTORS = {
    vmTableBody: '#vm-table-body',
    executeBtn: '#execute-btn',
    cancelBtn: '#cancel-btn',
    clearFilterBtn: '#clear-filter',
    clearGroupsBtn: '#clear-groups',
    groupsPlaceholder: '#groups-placeholder',
    groupFilterDisplay: '#group-filter-display',
    checkboxes: '#checkboxes',
    overSelect: '#over-select',
    messageContainer: '#message-container',
    groupCheckboxes: '.group-checkbox',
    selectBox: '#select-box',
    snapshotNameInput: '#snapshot-name-input',
    revertNameInput: '#revert-name-input',
    selectAllRevert: '#select-all-revert',
    operationCheckbox: '.operation-checkbox',
    operationSuccess: 'operation-success',
    operationError: 'operation-error',
    operationActive: 'operation-active',
};