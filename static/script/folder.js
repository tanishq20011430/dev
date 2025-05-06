// Get modal elements
const modal = document.getElementById('resultModal');
const resultTitle = document.getElementById('result-title');
const resultOutput = document.getElementById('result-output');
const modalHeader = document.getElementById('modal-header');
const modalFooter = document.querySelector('.modal-footer');

// Close modal only through OK button
document.querySelector('.ok-btn').addEventListener('click', () => {
    modal.style.display = 'none';
});

// Function to handle batch file execution
function runBatchFile(folder, file) {
    // Show loading state with spinner
    modal.style.display = 'block';
    modalHeader.className = 'loading';
    resultTitle.innerHTML = `<span class="loading-spinner"><i class="fas fa-spinner"></i></span> Running ${file}...`;
    resultOutput.textContent = 'Please wait while the file executes...';
    modalFooter.style.display = 'none';

    const downloadOutputBtn = document.getElementById('downloadOutputBtn');
    downloadOutputBtn.style.display = 'none';

    fetch(`/run_batch/${folder}/${file}`, {
        method: 'GET',
        headers: {
            'Accept': 'application/json',
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                modalHeader.className = 'success';
                resultTitle.textContent = 'Success';

                // Only show download button if output file exists
                if (data.new_file) {
                    // Update download link and show button
                    downloadOutputBtn.href = `/download_output/${data.new_file}`;
                    downloadOutputBtn.style.display = 'inline-flex';
                    downloadOutputBtn.innerHTML = '<i class="fas fa-download"></i> Download Output File';
                } else {
                    downloadOutputBtn.style.display = 'none';
                }
            } else {
                modalHeader.className = 'error';
                resultTitle.textContent = 'Error';
                downloadOutputBtn.style.display = 'none';
            }
            resultOutput.textContent = data.output || 'No output available';
            modalFooter.style.display = 'block';
        })
        .catch(error => {
            modalHeader.className = 'error';
            resultTitle.textContent = 'Error';
            resultOutput.textContent = 'Failed to execute batch file: ' + error.message;
            modalFooter.style.display = 'block';
            downloadOutputBtn.style.display = 'none';
        });
}
