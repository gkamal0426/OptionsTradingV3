/**
 * ===================================
 * Common Functions - Shared Across Pages
 * ===================================
 */

/**
 * Handle global user change (affects all pages)
 */
function handleGlobalUserChange() {
    const selectedUser = document.getElementById('globalUserSelect').value;
    console.log('Global user changed to:', selectedUser);
    
    // Store in sessionStorage to persist across pages
    sessionStorage.setItem('currentUser', selectedUser);
    
    // Reload current page data with new user
    if (typeof refreshPageData === 'function') {
        refreshPageData(selectedUser);
    }
}

/**
 * Handle global logout
 */
async function handleGlobalLogout() {
    if (confirm('Are you sure you want to logout?')) {
        try {
            const response = await fetch('/api/logout', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });
            
            const result = await response.json();
            
            // Redirect to login page
            window.location.href = '/';
            
        } catch (error) {
            console.error('Logout error:', error);
            // Force redirect anyway
            window.location.href = '/';
        }
    }
}

/**
 * Get current user from global selector or sessionStorage
 */
function getCurrentUser() {
    const selector = document.getElementById('globalUserSelect');
    if (selector) {
        return selector.value;
    }
    return sessionStorage.getItem('currentUser') || 'client1';
}

/**
 * Initialize global user selector on page load
 */
window.addEventListener('DOMContentLoaded', function() {
    const savedUser = sessionStorage.getItem('currentUser');
    if (savedUser) {
        const selector = document.getElementById('globalUserSelect');
        if (selector) {
            selector.value = savedUser;
        }
    }
});

/**
 * ===================================
 * Actions Dropdown — shared across all pages
 * ===================================
 */

function toggleActionsMenu() {
    const dropdown = document.getElementById('actionsDropdown');
    if (dropdown) dropdown.classList.toggle('show');
}

// Close the dropdown when clicking anywhere outside the button
window.addEventListener('click', function(event) {
    if (!event.target.matches('.actions-menu-btn')) {
        const dropdowns = document.getElementsByClassName('actions-dropdown-content');
        for (let i = 0; i < dropdowns.length; i++) {
            if (dropdowns[i].classList.contains('show')) {
                dropdowns[i].classList.remove('show');
            }
        }
    }
});

/** Utility: close the Actions dropdown */
function _closeActionsDropdown() {
    const dd = document.getElementById('actionsDropdown');
    if (dd) dd.classList.remove('show');
}

/**
 * Shared modal helper used by action handlers.
 * Falls back gracefully if the page has its own showModal.
 */
function _showActionResult(message, status) {
    if (typeof showModal === 'function') {
        showModal(message, status || 'info');
    } else {
        alert(message);
    }
}

async function handleOrders() {
    _closeActionsDropdown();
    try {
        const user = getCurrentUser();
        const ordersModal = document.getElementById('ordersModal');
        const ordersUserSelect = document.getElementById('ordersUserSelect');
        if (ordersModal) ordersModal.style.display = 'flex';
        if (ordersUserSelect) ordersUserSelect.value = user;
        if (typeof fetchOrders === 'function') {
            await fetchOrders(user);
        }
    } catch (error) {
        console.error('Error opening orders modal:', error);
    }
}

async function handleReUploadSymbols() {
    _closeActionsDropdown();
    const confirmed = confirm("Are you sure to reupload symbols and tokens, Click 'OK' to continue or 'Cancel' to skip");
    if (!confirmed) return;
    try {
        const response = await fetch('/api/reuploadsymbols', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const result = await response.json();
        _showActionResult(result.message, result.status);
    } catch (error) {
        console.error('Error:', error);
        _showActionResult('Re Upload Symbols failed', 'error');
    }
}

async function handleAddSymbols() {
    _closeActionsDropdown();
    const confirmed = confirm("Ensure symbols updated in excel file and Click 'OK' to add symbols or 'Cancel' to skip");
    if (!confirmed) return;
    try {
        const response = await fetch('/api/addsymbols', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const result = await response.json();
        _showActionResult(result.message, result.status);
    } catch (error) {
        console.error('Error:', error);
        _showActionResult('Add Symbols failed', 'error');
    }
}

async function handleAddStrikes() {
    _closeActionsDropdown();
    const confirmed = confirm("Ensure symbols updated in excel file and Click 'OK' to add symbols or 'Cancel' to skip");
    if (!confirmed) return;
    try {
        const response = await fetch('/api/addstrikes', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const result = await response.json();
        _showActionResult(result.message, result.status);
    } catch (error) {
        console.error('Error:', error);
        _showActionResult('Add Strikes failed', 'error');
    }
}

async function handleSubscribe() {
    _closeActionsDropdown();
    const confirmed = confirm("Ensure tokens updated in excel file and Click 'OK' to subscribe or 'Cancel' to skip");
    if (!confirmed) return;
    try {
        const response = await fetch('/api/subscribe', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const result = await response.json();
        _showActionResult(result.message, result.status);
    } catch (error) {
        console.error('Error:', error);
        _showActionResult('Subscribe failed', 'error');
    }
}

async function handleMcxDownload() {
    _closeActionsDropdown();
    try {
        const response = await fetch('/api/mcx_files', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const result = await response.json();
        _showActionResult(result.message, result.status);
    } catch (error) {
        console.error('Error:', error);
        _showActionResult('MCX Download failed', 'error');
    }
}