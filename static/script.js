let html5QrCode;
let currentCardId = null;

// Initialize scanner object
window.onload = function() {
    html5QrCode = new Html5Qrcode("reader");
};

function resetView() {
    // Hide all views, show menu
    document.getElementById('view-menu').classList.remove('hidden');
    document.getElementById('view-scanner').classList.add('hidden');
    document.getElementById('view-manual').classList.add('hidden');
    document.getElementById('view-form').classList.add('hidden');
    
    // Clear inputs
    document.getElementById('manual-card-id').value = '';
    document.getElementById('rental-note').value = '';
}

function showManualInput() {
    document.getElementById('view-menu').classList.add('hidden');
    document.getElementById('view-manual').classList.remove('hidden');
}

// Scanner logic
function startScanner() {
    document.getElementById('view-menu').classList.add('hidden');
    document.getElementById('view-scanner').classList.remove('hidden');

    html5QrCode.start(
        { facingMode: "environment" }, // Rear camera
        { fps: 10, qrbox: { width: 250, height: 250 } },
        onScanSuccess
    ).catch(err => {
        alert("Error starting camera: " + err);
        resetView();
    });
}

function stopScanner() {
    html5QrCode.stop().then(() => {
        resetView();
    }).catch(err => console.log(err));
}

function onScanSuccess(decodedText, decodedResult) {
    // Stop scanning
    html5QrCode.stop().then(() => {
        // Pass the scanned ID to the shared function
        handleCard(decodedText);
    });
}

// Manual input logic
function handleManualInput() {
    const inputId = document.getElementById('manual-card-id').value;
    if (inputId) {
        handleCard(inputId);
    } else {
        alert("Please enter a card number");
    }
}

// Shared function to handle card ID
function handleCard(cardId) {
    currentCardId = cardId;
    
    // Switch to the Form View
    document.getElementById('view-scanner').classList.add('hidden');
    document.getElementById('view-manual').classList.add('hidden');
    document.getElementById('view-form').classList.remove('hidden');
    
    // Show the ID to the user
    document.getElementById('display-card-id').innerText = cardId;
}

async function submitRental() {
    const note = document.getElementById('rental-note').value;
    
    // Send the card ID and note to the backend
    try {
        const response = await fetch('/api/rent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                card_id: currentCardId, 
                note: note 
            })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            alert("Rental Successful!");
            resetView();
        } else {
            alert("Error: " + data.message);
        }
    } catch (error) {
        alert("Error: " + error);
    }
}