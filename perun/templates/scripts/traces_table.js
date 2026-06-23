/* global formatNumber */
/* exported TRACES_TOOLTIPS, TracesTable */

const TRACES_TOOLTIPS = {
    trace: 'The function name. Click to view the call chain which shows how execution reached this function from the root caller.',
    baseline: 'The amount of resources consumed by the Unit/Trace in the baseline profile.',
    target: 'The amount of resources consumed by the Unit/Trace in the target profile.',
    prop_rel_delta: 'The difference between the relative resource consumption proportionally to the total baseline and target consumption change. For example, if the baseline and target consumed 2M and 1M CPU cycles in total, respectively, and a function \'foo\' consumed 100K cycles in both cases, the proportional difference is +5% as \'foo\' now consumes 10% total resources up from 5%.',
    abs_delta: 'The difference of Target - Baseline resource consumption. For example, if the baseline and target consumed 2M and 1M CPU cycles in total, respectively, and a function \'foo\' consumed 100K and 75K cycles in baseline, resp. target, the absolute difference is -25K.',
    rel_delta: 'The difference of Target - Baseline resource consumption in relative terms. For example, if the baseline and target consumed 2M and 1M CPU cycles in total, respectively, and a function \'foo\' consumed 100K and 80K cycles in baseline, resp. target, the relative difference is -20%.'
};

class TracesTable {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container with id '${containerId}' not found.`);
            return;
        }
        this.data = options.data || [];
        this.columns = options.columns || [];
        this.itemsPerPage = options.itemsPerPage || 10;
        this.enablePagination = options.enablePagination !== undefined ? options.enablePagination : true;
        this.enableFilters = options.enableFilters !== undefined ? options.enableFilters : true;
        this.onRowClick = options.onRowClick || null;
        this.currentPage = 1;
        this.sortColumn = options.initialSortColumn || null;
        this.sortDirection = options.initialSortDirection || 'asc';
        this.filters = {};
        this.regexModes = {};

        this.processedData = [...this.data];

        this.init();
    }

    init() {
        this.container.classList.add('traces-table-container');
        this.container.style.display = 'flex';
        this.container.style.flexDirection = 'column';
        this.render();
    }

    parseNumberInput(input) {
        if (input === null || input === undefined || input === '') return NaN;
        let str = String(input).trim().toUpperCase();

        str = str.replace(/\s/g, '');
        str = str.replace(',', '.');

        let multiplier = 1;
        if (str.endsWith('G')) {
            multiplier = 1e9;
            str = str.slice(0, -1);
        } else if (str.endsWith('M')) {
            multiplier = 1e6;
            str = str.slice(0, -1);
        } else if (str.endsWith('K')) {
            multiplier = 1e3;
            str = str.slice(0, -1);
        }

        const val = parseFloat(str);
        if (isNaN(val)) return NaN;
        return val * multiplier;
    }

    processData() {
        let result = [...this.data];

        Object.keys(this.filters).forEach(colKey => {
            const filterValue = this.filters[colKey];
            if (filterValue) {
                result = result.filter(row => {
                    const cellValue = row[colKey];

                    if (typeof filterValue === 'object' && (filterValue.min !== undefined || filterValue.max !== undefined)) {
                        const numValue = parseFloat(cellValue);
                        if (isNaN(numValue)) return false;

                        const minVal = this.parseNumberInput(filterValue.min);
                        const maxVal = this.parseNumberInput(filterValue.max);

                        if (!isNaN(minVal) && numValue < minVal) return false;
                        if (!isNaN(maxVal) && numValue > maxVal) return false;
                        return true;
                    }

                    const strCellValue = String(cellValue || '').toLowerCase();

                    if (this.regexModes[colKey]) {
                        try {
                            const regex = new RegExp(filterValue, 'i');
                            return regex.test(strCellValue);
                        } catch (e) {
                            return false; // Invalid regex, strict filtering
                        }
                    }

                    const strFilterValue = String(filterValue).toLowerCase();
                    return strCellValue.includes(strFilterValue);
                });
            }
        });

        if (this.sortColumn) {
            result.sort((a, b) => {
                let valA = a[this.sortColumn];
                let valB = b[this.sortColumn];

                const numA = parseFloat(valA);
                const numB = parseFloat(valB);
                if (!isNaN(numA) && !isNaN(numB)) {
                    valA = numA;
                    valB = numB;
                } else {
                    valA = String(valA).toLowerCase();
                    valB = String(valB).toLowerCase();
                }

                if (valA < valB) return this.sortDirection === 'asc' ? -1 : 1;
                if (valA > valB) return this.sortDirection === 'asc' ? 1 : -1;
                return 0;
            });
        }

        this.processedData = result;

        const maxPage = Math.ceil(this.processedData.length / this.itemsPerPage) || 1;
        if (this.currentPage > maxPage) {
            this.currentPage = 1;
        }
    }

    render() {
        const activeElement = document.activeElement;
        const activeElementId = activeElement ? activeElement.id : null;
        const selectionStart = activeElement ? activeElement.selectionStart : null;
        const selectionEnd = activeElement ? activeElement.selectionEnd : null;

        this.container.innerHTML = '';
        this.processData();

        const scrollContainer = document.createElement('div');
        scrollContainer.className = 'traces-table-scroll';

        const table = document.createElement('table');
        table.className = 'traces-table';

        table.appendChild(this.createHeader());
        table.appendChild(this.createBody());

        scrollContainer.appendChild(table);
        this.container.appendChild(scrollContainer);

        if (this.enablePagination) {
            this.container.appendChild(this.createPagination());
        }

        if (activeElementId) {
            const el = document.getElementById(activeElementId);
            if (el) {
                el.focus();
                if (selectionStart !== null && (el.type === 'text' || el.type === 'search' || el.type === 'password' || el.type === 'tel' || el.type === 'url' || el.type === 'number')) {
                    try {
                        el.setSelectionRange(selectionStart, selectionEnd);
                    } catch (e) {
                        console.warn('Could not set selection range', e);
                    }
                }
            }
        }
    }

    createHeader() {
        const thead = document.createElement('thead');
        const tr = document.createElement('tr');
        const filterTr = document.createElement('tr');
        filterTr.className = 'filter-row';

        this.columns.forEach((col, index) => {
            const th = document.createElement('th');
            th.innerText = col.title || col.data;

            if (col.tooltip) {
                const iconSpan = document.createElement('span');
                iconSpan.className = 'header-info-icon';
                iconSpan.title = col.tooltip;
                iconSpan.innerHTML = `{% include 'assets/info.svg' %}`;
                th.appendChild(iconSpan);
            }
            th.className = 'sortable';
            if (col.width) {
                th.style.width = col.width;
            }
            if (this.sortColumn === col.data) {
                th.classList.add(this.sortDirection);
            }
            th.addEventListener('click', () => {
                this.handleSort(col.data);
                this.render();
            });
            tr.appendChild(th);

            const thFilter = document.createElement('th');
            if (this.enableFilters && col.filterable !== false) {
                if (col.type === 'select') {
                    const select = document.createElement('select');
                    select.id = `filter-${col.data}`;

                    const uniqueValues = [...new Set(this.data.map(item => item[col.data]))].sort();

                    const defaultOption = document.createElement('option');
                    defaultOption.value = '';
                    defaultOption.innerText = '';
                    select.appendChild(defaultOption);

                    uniqueValues.forEach(val => {
                        const opt = document.createElement('option');
                        opt.value = val;
                        opt.innerText = val;
                        select.appendChild(opt);
                    });

                    select.value = this.filters[col.data] || '';
                    select.addEventListener('change', (e) => {
                        this.handleFilter(col.data, e.target.value);
                        this.render();
                    });
                    thFilter.appendChild(select);
                } else if (col.type === 'number') {
                    const container = document.createElement('div');
                    container.className = 'range-filter-container';

                    const minInput = document.createElement('input');
                    minInput.type = 'text';
                    minInput.placeholder = 'Min';
                    minInput.id = `filter-${col.data}-min`;
                    minInput.value = (this.filters[col.data] && this.filters[col.data].min) || '';
                    minInput.addEventListener('input', (e) => {
                        this.handleRangeFilter(col.data, 'min', e.target.value);
                        this.render();
                    });

                    const maxInput = document.createElement('input');
                    maxInput.type = 'text';
                    maxInput.placeholder = 'Max';
                    maxInput.id = `filter-${col.data}-max`;
                    maxInput.value = (this.filters[col.data] && this.filters[col.data].max) || '';
                    maxInput.addEventListener('input', (e) => {
                        this.handleRangeFilter(col.data, 'max', e.target.value);
                        this.render();
                    });

                    container.appendChild(minInput);
                    container.appendChild(maxInput);
                    thFilter.appendChild(container);
                } else {
                    const input = document.createElement('input');
                    input.type = 'text';
                    input.id = `filter-${col.data}`;
                    input.value = this.filters[col.data] || '';

                    if (col.data === 'uid') {
                        const wrapper = document.createElement('div');
                        wrapper.className = 'regex-filter-wrapper';

                        input.placeholder = this.regexModes[col.data] ? 'Regex...' : 'Filter...';

                        const toggleBtn = document.createElement('button');
                        toggleBtn.className = 'regex-toggle-btn';
                        toggleBtn.innerHTML = '.*';
                        toggleBtn.title = 'Toggle Regex Search';
                        if (this.regexModes[col.data]) {
                            toggleBtn.classList.add('active');
                        }

                        toggleBtn.addEventListener('click', (e) => {
                            e.stopPropagation();
                            this.regexModes[col.data] = !this.regexModes[col.data];
                            input.placeholder = this.regexModes[col.data] ? 'Regex...' : 'Filter...';
                            toggleBtn.classList.toggle('active');
                            this.handleFilter(col.data, input.value);
                            this.render();
                        });

                        wrapper.appendChild(input);
                        wrapper.appendChild(toggleBtn);
                        thFilter.appendChild(wrapper);
                    } else {
                        input.placeholder = 'Filter...';
                        thFilter.appendChild(input);
                    }

                    input.addEventListener('input', (e) => {
                        this.handleFilter(col.data, e.target.value);
                        this.render();
                    });
                }
            }
            if (this.enableFilters) {
                filterTr.appendChild(thFilter);
            }
        });

        thead.appendChild(tr);
        if (this.enableFilters) {
            thead.appendChild(filterTr);
        }
        return thead;
    }

    createBody() {
        const tbody = document.createElement('tbody');
        let pageData;
        let start = 0;

        if (this.enablePagination) {
            start = (this.currentPage - 1) * this.itemsPerPage;
            const end = start + this.itemsPerPage;
            pageData = this.processedData.slice(start, end);
        } else {
            pageData = this.processedData;
        }

        if (pageData.length === 0) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = this.columns.length;
            td.innerText = 'No data found';
            td.className = 'no-data';
            tr.appendChild(td);
            tbody.appendChild(tr);
            return tbody;
        }

        pageData.forEach((row, index) => {
            const tr = document.createElement('tr');
            const absoluteIndex = start + index;

            this.columns.forEach(col => {
                const td = document.createElement('td');
                let content = row[col.data];

                if (col.render && typeof col.render === 'function') {
                    td.innerHTML = col.render(content, row, absoluteIndex);
                } else {
                    if (col.formatNumber !== false && !isNaN(parseFloat(content)) && isFinite(content)) {
                        content = formatNumber(content);
                    }
                    if (col.data === 'uid') {
                        td.innerHTML = `<span class="trace-uid" style="display: block; width: 100%; height: 100%;" title="Click to view more details about the trace">${content !== undefined ? content : ''}</span>`;
                    } else {
                        td.innerText = content !== undefined ? content : '';
                    }
                }

                if (this.sortColumn === col.data) {
                    td.classList.add('sorted-column');
                }

                tr.appendChild(td);
            });

            if (this.onRowClick) {
                tr.style.cursor = 'pointer';
                tr.addEventListener('click', () => {
                    this.onRowClick(row, tr);
                });
            }

            tbody.appendChild(tr);
        });

        return tbody;
    }

    createPagination() {
        const pagination = document.createElement('div');
        pagination.className = 'traces-pagination';

        const totalPages = Math.ceil(this.processedData.length / this.itemsPerPage) || 1;
        const buttonContainer = document.createElement('div');
        buttonContainer.style.display = 'flex';
        buttonContainer.style.gap = '5px';

        const createBtn = (text, onClick, disabled = false, active = false) => {
            const btn = document.createElement('button');
            btn.innerHTML = text;
            btn.disabled = disabled;
            if (active) btn.classList.add('active');
            btn.addEventListener('click', onClick);
            return btn;
        };

        buttonContainer.appendChild(createBtn('&laquo;', () => {
            this.changePage(1);
            this.render();
        }, this.currentPage === 1));

        buttonContainer.appendChild(createBtn('&lsaquo;', () => {
            this.changePage(this.currentPage - 1);
            this.render();
        }, this.currentPage === 1));

        const rangeStart = Math.max(1, this.currentPage - 2);
        const rangeEnd = Math.min(totalPages, this.currentPage + 2);

        if (rangeStart > 1) {
            buttonContainer.appendChild(createBtn('1', () => {
                this.changePage(1);
                this.render();
            }, false, this.currentPage === 1));

            if (rangeStart > 2) {
                const ellipsis = document.createElement('span');
                ellipsis.innerText = '...';
                ellipsis.className = 'pagination-ellipsis';
                buttonContainer.appendChild(ellipsis);
            }
        }

        for (let i = rangeStart; i <= rangeEnd; i++) {
            if (i === 1 && rangeStart > 1) continue;

            buttonContainer.appendChild(createBtn(i.toString(), () => {
                this.changePage(i);
                this.render();
            }, false, this.currentPage === i));
        }

        if (rangeEnd < totalPages) {
            if (rangeEnd < totalPages - 1) {
                const ellipsis = document.createElement('span');
                ellipsis.innerText = '...';
                ellipsis.className = 'pagination-ellipsis';
                buttonContainer.appendChild(ellipsis);
            }
            buttonContainer.appendChild(createBtn(totalPages.toString(), () => {
                this.changePage(totalPages);
                this.render();
            }, false, this.currentPage === totalPages));
        }

        buttonContainer.appendChild(createBtn('&rsaquo;', () => {
            this.changePage(this.currentPage + 1);
            this.render();
        }, this.currentPage === totalPages));

        buttonContainer.appendChild(createBtn('&raquo;', () => {
            this.changePage(totalPages);
            this.render();
        }, this.currentPage === totalPages));

        const info = document.createElement('span');
        info.innerText = `Page ${this.currentPage} of ${totalPages} (${this.processedData.length} items)`;

        pagination.appendChild(buttonContainer);
        pagination.appendChild(info);

        const jumpContainer = document.createElement('div');
        jumpContainer.className = 'pagination-jump';

        const jumpInput = document.createElement('input');
        jumpInput.type = 'number';
        jumpInput.min = 1;
        jumpInput.max = totalPages;
        jumpInput.placeholder = 'Go to page';
        jumpInput.className = 'page-input';

        jumpInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                let page = parseInt(e.target.value, 10);
                if (isNaN(page)) return;

                if (page < 1) page = 1;
                if (page > totalPages) page = totalPages;

                this.changePage(page);
                this.render();
            }
        });

        jumpContainer.appendChild(jumpInput);
        pagination.appendChild(jumpContainer);

        return pagination;
    }

    handleSort(columnKey) {
        if (this.sortColumn === columnKey) {
            if (this.sortDirection === 'asc') {
                this.sortDirection = 'desc';
            } else if (this.sortDirection === 'desc') {
                this.sortColumn = null;
                this.sortDirection = 'asc';
            }
        } else {
            this.sortColumn = columnKey;
            this.sortDirection = 'asc';
        }
    }

    handleFilter(columnKey, value) {
        this.filters[columnKey] = value;
        this.currentPage = 1;
    }

    handleRangeFilter(columnKey, type, value) {
        if (!this.filters[columnKey] || typeof this.filters[columnKey] !== 'object') {
            this.filters[columnKey] = { min: '', max: '' };
        }
        this.filters[columnKey][type] = value;
        this.currentPage = 1;
    }

    changePage(newPage) {
        this.currentPage = newPage;
    }
}
