let html5QrCode;
let currentCardId = null;
let currentScanMode = 'card'; // Can be either 'card' or 'item'
let currentAction = null; // Can be 'rent' or 'return'
let rentedItems = [];


// Initialize scanner object
window.onload = function () {
    html5QrCode = new Html5Qrcode("reader");
};

function resetView() {
    document.getElementById('view-menu').classList.remove('hidden');
    document.getElementById('view-scanner').classList.add('hidden');
    document.getElementById('view-manual').classList.add('hidden');
    document.getElementById('view-action').classList.add('hidden');
    document.getElementById('view-form').classList.add('hidden');

    // Clear all data
    document.getElementById('manual-card-id').value = '';
    currentCardId = null;
    currentAction = null;
    rentedItems = [];
    updateItemsListUI(); // Clears the visual list
}

function showManualInput() {
    document.getElementById('view-menu').classList.add('hidden');
    document.getElementById('view-manual').classList.remove('hidden');
}

// REUSABLE SCANNER LOGIC

function startScanner(mode) {
    currentScanMode = mode; // card or item

    // Hide menus and forms, show the camera
    document.getElementById('view-menu').classList.add('hidden');
    document.getElementById('view-form').classList.add('hidden');
    document.getElementById('view-scanner').classList.remove('hidden');

    html5QrCode.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        onScanSuccess
    ).catch(err => {
        alert("Error starting camera: " + err);
        resetView();
    });
}

function stopScanner() {
    html5QrCode.stop().then(() => {
        // If an item scan is cancelled, go back to the form. Otherwise, go to main menu.
        if (currentScanMode === 'item') {
            showFormView();
        } else {
            resetView();
        }
    }).catch(err => console.log(err));
}

function onScanSuccess(decodedText, decodedResult) {
    html5QrCode.stop().then(() => {
        // Decide what to do with the text based on the current mode
        if (currentScanMode === 'card') {
            handleCard(decodedText);
        } else if (currentScanMode === 'item') {
            addItemToList(decodedText);
            showFormView(); // Send them back to the form to see their list
        }
    });
}


// --- CARD LOGIC ---

function handleManualInput() {
    const inputId = document.getElementById('manual-card-id').value;
    if (inputId && inputId.length == 6 && /^\d+$/.test(inputId)) {
        handleCard(inputId);
    } else {
        alert("Please enter a valid 6-digit card number");
    }
}

function handleCard(cardId) {
    currentCardId = cardId;

    document.getElementById('display-action-card-id').innerText = cardId;
    document.getElementById('display-card-id').innerText = cardId;

    document.getElementById('view-scanner').classList.add('hidden');
    document.getElementById('view-manual').classList.add('hidden');
    document.getElementById('view-action').classList.remove('hidden');
}

function showFormView() {
    document.getElementById('view-scanner').classList.add('hidden');
    document.getElementById('view-manual').classList.add('hidden');
    document.getElementById('view-menu').classList.add('hidden');
    document.getElementById('view-form').classList.remove('hidden');
}


function selectAction(action) {
    currentAction = action;

    const submitBtn = document.getElementById('btn_submit');
    if (action === 'rent') {
        submitBtn.innerText = 'Confirm Rental';
        submitBtn.className = 'btn-success';
    } else {
        submitBtn.innerText = 'Confirm Return';
        submitBtn.className = 'btn-sucess';
    }

    document.getElementById('view-action').classList.add('hidden');
    showFormView();
}


// MULTIPLE ITEMS LOGIC

function addManualItem() {
    const inputField = document.getElementById('manual-item-input');
    const itemText = inputField.value.trim();

    if (itemText) {
        addItemToList(itemText);
        inputField.value = ''; // Clear the input field after adding
    }
}

function addItemToList(itemText) {
    rentedItems.push(itemText);
    updateItemsListUI();
}

function removeItem(index) {
    rentedItems.splice(index, 1); // Remove 1 item at the specific index
    updateItemsListUI();
}

function updateItemsListUI() {
    const listEl = document.getElementById('items-list');
    listEl.innerHTML = ''; // Clear the current HTML list

    // Rebuild the HTML list from our array
    rentedItems.forEach((item, index) => {
        const li = document.createElement('li');
        li.innerText = item + " ";

        // Add a remove button for each item
        const removeBtn = document.createElement('span');
        removeBtn.innerText = '❌';
        removeBtn.style.cursor = 'pointer';
        removeBtn.onclick = () => removeItem(index);

        li.appendChild(removeBtn);
        listEl.appendChild(li);
    });
}

// --- SUBMIT LOGIC ---

async function submitTransaction() {
    if (rentedItems.length === 0) {
        alert("Please add at least one item.");
        return;
    }

    // Items are joined into a single comma-separated string
    const joinedItems = rentedItems.join(', ');

    try {
        const response = await fetch('/api/transaction', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_id: currentCardId,
                note: joinedItems,
                action: currentAction // Send rent or return
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            alert((currentAction === 'rent' ? "Rental" : "Return") + " Successful!\nItems: " + joinedItems);
            resetView();
            
        } else {
            alert("Error: " + data.message);
        }
    } catch (error) {
        alert("Error: " + error);
    }
}