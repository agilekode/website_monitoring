document.getElementById('loginForm').addEventListener('submit', function(event) {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();

    if (username === '' || password === '') {
        event.preventDefault();
        alert('Username and password cannot be empty!');
    }
});

function toggleManualEntry() {
    const manualEntryCheckbox = document.getElementById('manualEntry');
    const fileUploadSection = document.getElementById('fileUploadSection');
    const manualEntrySection = document.getElementById('manualEntrySection');
    const fileInput = document.getElementById('file');

    if (manualEntryCheckbox.checked) {
        fileUploadSection.style.display = 'none';
        manualEntrySection.style.display = 'block';
        fileInput.value = "";
    } else {
        fileUploadSection.style.display = 'block';
        manualEntrySection.style.display = 'none';
    }
}
