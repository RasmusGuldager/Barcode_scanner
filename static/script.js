let html5QrCode;
let currentCardId = null;
let currentEmail = null;
let currentName = null;
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
    document.getElementById('view-register').classList.add('hidden'); // Skjul den nye skærm
    document.getElementById('view-action').classList.add('hidden');
    document.getElementById('view-form').classList.add('hidden');

    document.getElementById('email-input').value = '';
    document.getElementById('reg-name').value = '';
    document.getElementById('reg-email').value = '';

    currentCardId = null;
    currentEmail = null;
    currentName = null;
    currentAction = null;
    rentedItems = [];
    updateItemsListUI();
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
            handleCard(decodedText, null);
        } else if (currentScanMode === 'item') {
            addItemToList(decodedText);
            showFormView(); // Send them back to the form to see their list
        }
    });
}


// --- CARD LOGIC ---

function handleManualInput() {
    const inputEmail = document.getElementById('email-input').value;
    if (inputEmail && inputEmail.includes('@') && inputEmail.includes('.')) {
        handleCard(null, inputEmail);
    } else {
        alert("Please enter a valid e-mail address");
    }
}

async function handleCard(cardId = null, email = null) {
    currentCardId = cardId;
    currentEmail = email;

    document.getElementById('view-menu').classList.add('hidden');
    document.getElementById('view-scanner').classList.add('hidden');
    document.getElementById('view-manual').classList.add('hidden');

    try {
        const response = await fetch('/api/check_user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ card_id: cardId, email: email })
        });
        const data = await response.json();

        if (data.exists) {
            currentEmail = data.email;
            currentName = data.name;
            showActionView();
        } else {
            document.getElementById('view-register').classList.remove('hidden');
            if (email) {
                document.getElementById('reg-email').value = email;
            }
        }
    } catch (error) {
        alert("Error checking user database: " + error);
        resetView();
    }
}


function completeRegistration() {
    const nameInput = document.getElementById('reg-name').value.trim();
    const emailInput = document.getElementById('reg-email').value.trim();

    if (!nameInput || !emailInput) {
        alert("Please provide both Name and Email.");
        return;
    }

    currentName = nameInput;
    currentEmail = emailInput;

    document.getElementById('view-register').classList.add('hidden');
    showActionView();
}


function showActionView() {
    const displayEmail = currentEmail;
    document.getElementById('display-action-mail').innerText = displayEmail;
    document.getElementById('display-mail').innerText = displayEmail;
    
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
        submitBtn.className = 'btn-success';
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
                email: currentEmail,
                name: currentName,
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