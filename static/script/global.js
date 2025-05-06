// Menu toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    const menuToggle = document.getElementById('menuToggle');
    const menuClose = document.getElementById('menuClose');
    const mainNav = document.getElementById('mainNav');
    const menuOverlay = document.getElementById('menuOverlay');

    // Check if elements exist before adding event listeners
    if (!menuToggle || !menuClose || !mainNav || !menuOverlay) {
        console.error('One or more menu elements not found:', { menuToggle, menuClose, mainNav, menuOverlay });
        return; // Exit if elements are missing
    }

    // Open menu function
    function openMenu() {
        mainNav.classList.add('active');
        menuOverlay.classList.add('active');
        document.body.style.overflow = 'hidden'; // Prevent scrolling when menu is open
    }

    // Close menu function
    function closeMenu() {
        mainNav.classList.remove('active');
        menuOverlay.classList.remove('active');
        document.body.style.overflow = ''; // Restore scrolling
        
        // Close any open dropdowns
        document.querySelectorAll('.dropdown-menu').forEach(dropdown => {
            dropdown.classList.remove('show');
        });
    }

    // Toggle menu open
    menuToggle.addEventListener('click', function(e) {
        e.preventDefault();
        openMenu();
    });

    // Close menu button
    menuClose.addEventListener('click', function(e) {
        e.preventDefault();
        closeMenu();
    });

    // Close menu when clicking overlay (only if click is directly on overlay, not on menu)
    menuOverlay.addEventListener('click', function(e) {
        // Only close if the click is directly on the overlay, not on the menu
        if (e.target === menuOverlay) {
            closeMenu();
        }
    });    // ESC key to close menu
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeMenu();
            
            // Also close any open dropdowns
            document.querySelectorAll('.dropdown-menu, .header-user-menu').forEach(dropdown => {
                dropdown.classList.remove('show');
            });
        }
    });

    // Toggle header user menu dropdown
    const headerUserToggle = document.getElementById('headerUserToggle');
    const headerUserMenu = document.getElementById('headerUserMenu');
    if (headerUserToggle && headerUserMenu) {
        headerUserToggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            headerUserMenu.classList.toggle('show');
            
            // Close other dropdowns
            const predefinedQueriesMenu = document.getElementById('predefinedQueriesMenu');
            const userDropdownMenu = document.getElementById('dropdownMenu');
            
            if (predefinedQueriesMenu) {
                predefinedQueriesMenu.classList.remove('show');
            }
            
            if (userDropdownMenu) {
                userDropdownMenu.classList.remove('show');
            }
        });
    }

    // Handle standard menu links - these should navigate normally
    const standardLinks = mainNav.querySelectorAll('a:not(.dropdown-toggle):not([data-special])');
    standardLinks.forEach(link => {
        // Let standard links navigate normally - no preventDefault here
        // We don't need to add special handling for these links
    });

    // Toggle dropdown menu for user account
    const userDropdown = document.getElementById('userDropdown');
    const dropdownMenu = document.getElementById('dropdownMenu');
    if (userDropdown && dropdownMenu) {
        userDropdown.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            dropdownMenu.classList.toggle('show');
            // Close other dropdowns
            const otherDropdown = document.getElementById('predefinedQueriesMenu');
            if (otherDropdown) {
                otherDropdown.classList.remove('show');
            }
        });
    }

    // Toggle predefined queries dropdown
    const predefinedQueriesDropdown = document.getElementById('predefinedQueriesDropdown');
    const predefinedQueriesMenu = document.getElementById('predefinedQueriesMenu');
    if (predefinedQueriesDropdown && predefinedQueriesMenu) {
        predefinedQueriesDropdown.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Toggle the dropdown
            predefinedQueriesMenu.classList.toggle('show');
            
            // Check if dropdown is now visible
            if (predefinedQueriesMenu.classList.contains('show')) {
                // Ensure enough space below the dropdown
                const dropdownHeight = predefinedQueriesMenu.offsetHeight;
                const dropdownParent = predefinedQueriesDropdown.closest('.predefined-queries-dropdown');
                if (dropdownParent) {
                    // Add temporary class for expanded state with margin
                    dropdownParent.classList.add('menu-expanded');
                }
            } else {
                // Remove expanded state when closed
                const dropdownParent = predefinedQueriesDropdown.closest('.predefined-queries-dropdown');
                if (dropdownParent) {
                    dropdownParent.classList.remove('menu-expanded');
                }
            }
            
            // Close other dropdowns
            const otherDropdown = document.getElementById('dropdownMenu');
            if (otherDropdown) {
                otherDropdown.classList.remove('show');
            }
        });
    }

    // Handle dropdown menu items
    document.querySelectorAll('.dropdown-menu a').forEach(link => {
        if (!link.hasAttribute('data-special')) {
            // For regular dropdown links (like logout), just let them navigate
            // The menu will be closed by the link navigation naturally
        }
    });

    // Predefined queries functionality - special handling for AJAX links
    document.querySelectorAll('#predefinedQueriesMenu a').forEach(link => {
        link.setAttribute('data-special', 'true');
        link.addEventListener('click', async function(e) {
            e.preventDefault();
            e.stopPropagation();
            const href = this.getAttribute('href');
            const queryType = href.substring(href.lastIndexOf('/') + 1);

            // Show loading overlay
            const loadingOverlay = document.getElementById('loadingOverlay');
            if (loadingOverlay) loadingOverlay.style.display = 'flex';

            try {
                const response = await fetch(`/execute_predefined_query/${queryType}`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();
                if (data.success) {
                    window.open(data.redirect_url, '_blank');
                    closeMenu(); // Close menu after opening new tab
                } else {
                    alert(`Error executing query: ${data.error}`);
                }
            } catch (error) {
                alert(`Error: ${error.message}`);
            } finally {
                // Hide loading overlay
                if (loadingOverlay) loadingOverlay.style.display = 'none';
            }
        });
    });

    // Add a global click handler to close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        // Only if the menu is open and the click is outside dropdown toggles and menus
        if (!e.target.closest('.dropdown-toggle') && !e.target.closest('.dropdown-menu')) {
            document.querySelectorAll('.dropdown-menu').forEach(dropdown => {
                dropdown.classList.remove('show');
            });
            
            // Remove expanded state from all dropdown containers
            document.querySelectorAll('.menu-expanded').forEach(container => {
                container.classList.remove('menu-expanded');
            });
        }
        
        // Collapse menu if click is outside menu and toggle button, and menu is open
        if (
            mainNav.classList.contains('active') &&
            !e.target.closest('#mainNav') &&
            !e.target.closest('#menuToggle')
        ) {
            closeMenu();
        }
    });

    // Prevent menu from closing when clicking inside the menu
    // But still allow link navigation
    mainNav.addEventListener('click', function(e) {
        e.stopPropagation(); // Stop click from reaching document
        
        // If this is not a link or button click, don't do anything else
        if (!e.target.closest('a') && !e.target.closest('button')) {
            return;
        }
        
        // Handle dropdown toggles separately
        if (e.target.closest('.dropdown-toggle')) {
            return; // We already have handlers for these
        }
        
        // For regular links, let the browser handle them normally
        // No preventDefault() here so links work as expected
    });
});