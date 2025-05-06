let allData = [], filteredData = [];
const pageSize = 10;
let currentPage = 1;
let sortState = {};
let advancedFilters = {};

window.onload = async function () {
    try {
        const response = await fetch(window.CSV_URL);
        const csvText = await response.text();
        allData = parseCSV(csvText);
        filteredData = [...allData];
        updateTable();
        initializeFilters();
        addSortAndFilterListeners();
    } catch (error) {
        console.error('Error loading data:', error);
    }
};

function parseCSV(csv) {
    const lines = csv.split('\n');
    const headers = lines[0].split(',');
    const result = [];
    for (let i = 1; i < lines.length; i++) {
        if (!lines[i].trim()) continue;
        const obj = {};
        const currentline = lines[i].split(',');
        for (let j = 0; j < headers.length; j++) {
            obj[headers[j]] = currentline[j];
        }
        result.push(obj);
    }
    return result;
}

function initializeFilters() {
    document.querySelectorAll('.filter-input').forEach(input => {
        input.addEventListener('input', function () {
            clearTimeout(input._debounce);
            input._debounce = setTimeout(filterData, 200);
        });
    });
}

function addSortAndFilterListeners() {
    document.querySelectorAll('.sort-asc').forEach(icon => {
        icon.addEventListener('click', () => {
            sortState = { column: icon.dataset.column, order: 'asc' };
            sortData();
            updateTable();
        });
    });
    document.querySelectorAll('.sort-desc').forEach(icon => {
        icon.addEventListener('click', () => {
            sortState = { column: icon.dataset.column, order: 'desc' };
            sortData();
            updateTable();
        });
    });
    document.querySelectorAll('.filter-icon').forEach(icon => {
        icon.addEventListener('click', (e) => {
            e.stopPropagation();
            document.querySelectorAll('.filter-icon').forEach(i => i.classList.remove('active'));
            icon.classList.add('active');
            showFilterDropdown(icon.dataset.column, icon);
        });
    });
    document.addEventListener('click', () => {
        let dd = document.getElementById('active-filter-dropdown');
        if (dd) dd.remove();
        document.querySelectorAll('.filter-icon').forEach(i => i.classList.remove('active'));
    });
}

document.getElementById('clearFiltersBtn').addEventListener('click', () => {
    // Clear text filters
    document.querySelectorAll('.filter-input').forEach(input => input.value = '');
    // Clear advanced filters
    advancedFilters = {};
    // Remove any open filter dropdown
    let dd = document.getElementById('active-filter-dropdown');
    if (dd) dd.remove();
    // Reset data
    filterData();
});

function sortData() {
    if (!sortState.column) return;
    const { column: col, order } = sortState;
    filteredData.sort((a, b) => {
        let va = a[col] || '', vb = b[col] || '';
        let na = parseFloat(va), nb = parseFloat(vb);
        if (!isNaN(na) && !isNaN(nb)) { va = na; vb = nb; }
        if (va < vb) return order === 'asc' ? -1 : 1;
        if (va > vb) return order === 'asc' ? 1 : -1;
        return 0;
    });
}

function showFilterDropdown(column, iconElem) {
    // Remove any existing dropdown from body
    let existing = document.getElementById('active-filter-dropdown');
    if (existing) existing.remove();

    // Create dropdown
    const dropdown = document.createElement('div');
    dropdown.className = 'filter-dropdown';
    dropdown.id = 'active-filter-dropdown';
    dropdown.setAttribute('data-column', column);
    dropdown.style.position = 'absolute';
    dropdown.style.display = 'block';
    dropdown.style.zIndex = 2000;

    // Unique values for the column
    const values = Array.from(new Set(allData.map(row => row[column] ?? ''))).sort();
    let checkedArr = Array.isArray(advancedFilters[column]) ? advancedFilters[column] : values;

    // Scrollable container for filter options
    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'filter-options-scroll';

    // "Select All"
    const allChecked = checkedArr.length === values.length;
    const selectAll = document.createElement('div');
    selectAll.innerHTML = `<label><input type="checkbox" class="filter-select-all" ${allChecked ? 'checked' : ''}> (Select All)</label>`;
    optionsContainer.appendChild(selectAll);

    // Value checkboxes
    values.forEach(val => {
        const checked = checkedArr.includes(val) ? 'checked' : '';
        const item = document.createElement('div');
        item.innerHTML = `<label><input type="checkbox" class="filter-checkbox" data-value="${val}" ${checked}> ${val || '(Blank)'}</label>`;
        optionsContainer.appendChild(item);
    });

    dropdown.appendChild(optionsContainer);

    // Sticky footer for Apply button
    const footer = document.createElement('div');
    footer.className = 'filter-dropdown-footer';
    const applyBtn = document.createElement('button');
    applyBtn.textContent = 'Apply';
    applyBtn.className = 'btn';
    applyBtn.style.width = '100%';
    applyBtn.onclick = (e) => {
        e.stopPropagation();
        const checkedVals = Array.from(dropdown.querySelectorAll('.filter-checkbox:checked')).map(cb => cb.dataset.value);
        if (checkedVals.length === values.length || checkedVals.length === 0) {
            delete advancedFilters[column];
        } else {
            advancedFilters[column] = checkedVals;
        }
        filterData();
        dropdown.remove();
        iconElem.classList.remove('active');
    };
    footer.appendChild(applyBtn);
    dropdown.appendChild(footer);

    // Select All logic
    optionsContainer.querySelector('.filter-select-all').addEventListener('change', function () {
        const checked = this.checked;
        optionsContainer.querySelectorAll('.filter-checkbox').forEach(cb => cb.checked = checked);
    });

    // Individual checkbox logic
    optionsContainer.querySelectorAll('.filter-checkbox').forEach(cb => {
        cb.addEventListener('change', function () {
            const allCbs = optionsContainer.querySelectorAll('.filter-checkbox');
            const checkedCbs = optionsContainer.querySelectorAll('.filter-checkbox:checked');
            optionsContainer.querySelector('.filter-select-all').checked = (allCbs.length === checkedCbs.length);
        });
    });

    dropdown.onclick = e => e.stopPropagation();

    // Position dropdown below the icon
    document.body.appendChild(dropdown);
    const iconRect = iconElem.getBoundingClientRect();
    dropdown.style.left = (iconRect.left + window.scrollX) + 'px';
    dropdown.style.top = (iconRect.bottom + window.scrollY + 2) + 'px';
}

function filterData() {
    const filters = {};
    document.querySelectorAll('.filter-input').forEach(input => {
        const column = input.dataset.column;
        const value = input.value.trim().toLowerCase();
        if (value) filters[column] = value;
    });

    filteredData = allData.filter(row => {
        // Text filter
        const textMatch = Object.entries(filters).every(([column, filterValue]) => {
            const cellValue = String(row[column] ?? '').toLowerCase();
            return cellValue.includes(filterValue);
        });
        // Advanced filter
        const advMatch = Object.entries(advancedFilters).every(([column, valArr]) => {
            if (!valArr || valArr.length === 0) return true;
            return valArr.includes(row[column] ?? '');
        });
        return textMatch && advMatch;
    });

    currentPage = 1;
    sortData();
    updateTable();
}

function updateTable() {
    const totalPages = Math.ceil(filteredData.length / pageSize);
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    const pageData = filteredData.slice(start, end);

    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';

    if (pageData.length === 0) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = Object.keys(allData[0] || {}).length || 1;
        td.textContent = 'No data available.';
        tr.appendChild(td);
        tbody.appendChild(tr);
    } else {
        pageData.forEach(row => {
            const tr = document.createElement('tr');
            Object.values(row).forEach(value => {
                const td = document.createElement('td');
                td.textContent = value;
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    document.getElementById('currentPage').textContent = currentPage;
    document.getElementById('totalPages').textContent = totalPages || 1;
    document.getElementById('prevPage').disabled = currentPage === 1;
    document.getElementById('nextPage').disabled = currentPage === totalPages || totalPages === 0;
}

document.getElementById('prevPage').addEventListener('click', () => {
    if (currentPage > 1) {
        currentPage--;
        updateTable();
    }
});

document.getElementById('nextPage').addEventListener('click', () => {
    const totalPages = Math.ceil(filteredData.length / pageSize);
    if (currentPage < totalPages) {
        currentPage++;
        updateTable();
    }
});

document.getElementById('exportBtn').addEventListener('click', () => {
    const headers = Object.keys(filteredData[0]).join(',');
    const rows = filteredData.map(row => Object.values(row).join(','));
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('hidden', '');
    a.setAttribute('href', url);
    a.setAttribute('download', 'filtered_query_results.csv');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
});
