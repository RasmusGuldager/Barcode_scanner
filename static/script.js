let html5QrCode;

const state = {
    cardId: null,
    email: null,
    name: null,
    scanMode: 'card', // 'card' or 'item'
    action: null,     // 'rent' or 'return'
    rentedItems: []
};

window.onload = function () {
    html5QrCode = new Html5Qrcode("reader");
};


const $ = (id) => document.getElementById(id);

// Helper function to show/hide views based on their IDs
function showView(viewIdToShow) {
    const allViews = ['view-menu', 'view-scanner', 'view-manual', 'view-register', 'view-action', 'view-form'];

    // Hide all
    allViews.forEach(id => {
        $(id).classList.add('hidden');
    });

    // Show the requested view
    if (viewIdToShow) {
        $(viewIdToShow).classList.remove('hidden');
    }
}



function resetView() {
    showView('view-menu');

    // reset form fields
    $('email-input').value = '';
    $('reg-name').value = '';
    $('reg-email').value = '';

    // reset states
    state.cardId = null;
    state.email = null;
    state.name = null;
    state.action = null;
    state.rentedItems = [];

    updateItemsListUI();
}

function showManualInput() {
    showView('view-manual');
}


function showActionView() {
    // Opdaterer teksten på skærmen med den aktuelle email
    $('display-action-mail').innerText = state.email;
    $('display-mail').innerText = state.email;

    showView('view-action');
}


function selectAction(action) {
    state.action = action;

    const submitBtn = $('btn_submit');
    if (action === 'rent') {
        submitBtn.innerText = 'Confirm Rental';
        submitBtn.className = 'btn-success';
    } else {
        submitBtn.innerText = 'Confirm Return';
        submitBtn.className = 'btn-success';
    }

    showView('view-form');
}




// SCANNER LOGIC

function startScanner(mode) {
    state.scanMode = mode;

    showView('view-scanner');

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
        if (state.scanMode === 'item') {
            showView('view-form');
        } else {
            resetView();
        }
    }).catch(err => console.log(err));
}

function onScanSuccess(decodedText, decodedResult) {
    html5QrCode.stop().then(() => {
        // Decide what to do with the text based on the current mode
        if (state.scanMode === 'card') {
            handleCard(decodedText, null);
        } else if (state.scanMode === 'item') {
            addItemToList(decodedText);
            showView('view-form'); // Send them back to the form to see their list
        }
    });
}




// CARD LOGIC

function handleManualInput() {
    const inputEmail = $('email-input').value;
    if (inputEmail && inputEmail.includes('@') && inputEmail.includes('.')) {
        handleCard(null, inputEmail);
    } else {
        alert("Please enter a valid e-mail address");
    }
}

async function handleCard(cardId = null, email = null) {
    state.cardId = cardId;
    state.email = email;

    showView(null); // Hide all views while we check the database

    try {
        const response = await fetch('/api/check_user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ card_id: cardId, email: email })
        });
        const data = await response.json();

        if (data.exists) {
            state.email = data.email;
            state.name = data.name;
            showActionView();
        } else {
            showView('view-register');
            if (email) {
                $('reg-email').value = email;
            }
        }
    } catch (error) {
        alert("Error checking user database: " + error);
        resetView();
    }
}


function completeRegistration() {
    const nameInput = $('reg-name').value.trim();
    const emailInput = $('reg-email').value.trim();

    if (!nameInput || !emailInput) {
        alert("Please provide both Name and Email.");
        return;
    }

    state.name = nameInput;
    state.email = emailInput;

    showActionView();
}



// MULTIPLE ITEMS LOGIC

function addManualItem() {
    const inputField = $('manual-item-input');
    const itemText = inputField.value.trim();

    if (itemText) {
        addItemToList(itemText);
        inputField.value = ''; // Clear the input field after adding
    }
}

function addItemToList(itemText) {
    state.rentedItems.push(itemText);
    updateItemsListUI();
}

function removeItem(index) {
    state.rentedItems.splice(index, 1); // Remove 1 item at the specific index
    updateItemsListUI();
}

function updateItemsListUI() {
    const listEl = $('items-list');
    listEl.innerHTML = ''; // Clear the current HTML list

    // Rebuild the HTML list from our array
    state.rentedItems.forEach((item, index) => {
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
    if (state.rentedItems.length === 0) {
        alert("Please add at least one item.");
        return;
    }

    // Items are joined into a single comma-separated string
    const joinedItems = state.rentedItems.join(', ');

    try {
        const response = await fetch('/api/transaction', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_id: state.cardId,
                email: state.email,
                name: state.name,
                note: joinedItems,
                action: state.action // Send rent or return
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            alert((state.action === 'rent' ? "Rental" : "Return") + " Successful!\nItems: " + joinedItems);
            resetView();

        } else {
            alert("Error: " + data.message);
        }
    } catch (error) {
        alert("Error: " + error);
    }
}