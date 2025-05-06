// Query execution function
async function executeQuery() {
    const query = document.getElementById('queryInput').value.trim().replace(/;$/, '');
    const schema = document.getElementById('schemaSelect').value;
    const resultsDiv = document.getElementById('results');
    
    try {
        resultsDiv.innerHTML = '<p>Executing query...</p>';

        const response = await fetch('/execute_query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query, schema })
        });
        
        const data = await response.json();
        if (data.success) {
            // Open SQL output page in new tab
            window.open(data.redirect_url, '_blank');
        } else {
            resultsDiv.innerHTML = `<p class="error-message">Error: ${data.error}</p>`;
        }
    } catch (error) {
        resultsDiv.innerHTML = `<p class="error-message">Error: ${error.message}</p>`;
    }
}