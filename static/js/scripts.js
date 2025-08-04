let originalRows = [];

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        const notification = document.getElementById('copy-notification');
        if (notification) {
            notification.style.display = 'block';
            setTimeout(() => {
                notification.style.display = 'none';
            }, 2000);
        }
    });
}

function copyLink(button) {
    const url = button.getAttribute('data-url');
    navigator.clipboard.writeText(url);
    const copyIcon = button.querySelector('.copy-icon');
    const checkIcon = button.querySelector('.check-icon');
    if (button && copyIcon && checkIcon) {
        button.classList.add('copy-anim');
        copyIcon.classList.add('hidden');
        checkIcon.classList.remove('hidden');
        setTimeout(() => {
            button.classList.remove('copy-anim');
            copyIcon.classList.remove('hidden');
            checkIcon.classList.add('hidden');
        }, 500);
    }
}

function openLogoutModal() {
    const modal = document.getElementById('logout-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeLogoutModal() {
    const modal = document.getElementById('logout-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function openEditModal(shortCode) {
    const modal = document.getElementById('edit-modal');
    const form = document.getElementById('edit-form');
    if (modal && form) {
        form.action = `/update/${shortCode}`;
        modal.style.display = 'flex';
    }
}

function closeEditModal() {
    const modal = document.getElementById('edit-modal');
    if (modal) {
        modal.style.display = 'none';
        document.getElementById('new_code').value = '';
        document.getElementById('code-error').style.display = 'none';
    }
}

function openDeleteModal(shortCode) {
    const modal = document.getElementById('delete-modal');
    const form = document.getElementById('delete-form');
    if (modal && form) {
        form.action = `/delete/${shortCode}`;
        modal.style.display = 'flex';
    }
}

function closeDeleteModal() {
    const modal = document.getElementById('delete-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function openBulkDeleteModal() {
    const modal = document.getElementById('bulk-delete-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeBulkDeleteModal() {
    const modal = document.getElementById('bulk-delete-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function toggleSelectAll() {
    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('.link-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAll.checked;
    });
    updateDeleteButton();
}

function updateDeleteButton() {
    const checkboxes = document.querySelectorAll('.link-checkbox');
    const deleteButton = document.getElementById('bulk-delete-button');
    const anyChecked = Array.from(checkboxes).some(checkbox => checkbox.checked);
    if (deleteButton) {
        deleteButton.disabled = !anyChecked;
        deleteButton.classList.toggle('opacity-50', !anyChecked);
        deleteButton.classList.toggle('cursor-not-allowed', !anyChecked);
    }
}

function applyFilters() {
    const searchTerm = document.getElementById('search-bar').value.toLowerCase();
    const contentType = document.getElementById('content_type_filter').value;
    const tableBody = document.getElementById('links-table-body');
    const noLinksMessage = document.getElementById('no-links-message');
    
    if (!tableBody) return;

    tableBody.innerHTML = '';
    let visibleRows = 0;

    originalRows.forEach(row => {
        const shortCode = row.dataset.shortCode.toLowerCase();
        const content = row.dataset.content.toLowerCase();
        const rowContentType = row.dataset.contentType;
        
        const matchesSearch = !searchTerm || shortCode.includes(searchTerm) || content.includes(searchTerm);
        const matchesFilter = !contentType || rowContentType === contentType;
        
        if (matchesSearch && matchesFilter) {
            tableBody.appendChild(row.cloneNode(true));
            visibleRows++;
        }
    });

    if (noLinksMessage) {
        noLinksMessage.style.display = visibleRows === 0 ? 'block' : 'none';
    }

    updateDeleteButton();
}

document.addEventListener('DOMContentLoaded', () => {
    const tableBody = document.getElementById('links-table-body');
    if (tableBody) {
        originalRows = Array.from(tableBody.querySelectorAll('tr'));
    }
    
    const searchBar = document.getElementById('search-bar');
    const contentTypeFilter = document.getElementById('content_type_filter');
    
    if (searchBar) {
        searchBar.addEventListener('input', applyFilters);
    }
    
    if (contentTypeFilter) {
        contentTypeFilter.addEventListener('change', applyFilters);
    }

    document.querySelectorAll('.ripple').forEach(button => {
        button.addEventListener('click', function(e) {
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const ripple = document.createElement('span');
            ripple.style.position = 'absolute';
            ripple.style.background = 'rgba(255, 255, 255, 0.3)';
            ripple.style.borderRadius = '50%';
            ripple.style.transform = 'scale(0)';
            ripple.style.animation = 'ripple-effect 0.6s ease-out';
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            this.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
        });
    });
});

function updateDateTime() {
    const now = new Date();
    const options = {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZone: 'Asia/Jakarta'
    };
    const datetimeElement = document.getElementById('datetime');
    if (datetimeElement) {
        datetimeElement.textContent = now.toLocaleString('id-ID', options);
    }
}

updateDateTime();
setInterval(updateDateTime, 1000);

document.querySelectorAll('.copy-button').forEach(button => {
    button.addEventListener('click', () => copyLink(button));
});