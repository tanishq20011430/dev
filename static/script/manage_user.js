// Delete user functionality
document.querySelectorAll('.delete-user').forEach(button => {
    button.addEventListener('click', function() {
        const username = this.dataset.username;
        
        if (confirm(`Are you sure you want to delete user "${username}"?`)) {
            fetch(`/delete_user/${username}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Remove the user from the UI
                    this.closest('.user-item').remove();
                } else {
                    alert(`Error: ${data.error || 'Could not delete user'}`);
                }
            })
            .catch(error => {
                alert(`Error: ${error}`);
            });
        }
    });
});

// Example: document.querySelector('.user-name').textContent = username.toUpperCase();