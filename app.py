from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Serve the HTML file
@app.route('/')
def home():
    return render_template('index.html')

# The API Endpoint your JS calls
@app.route('/api/rent', methods=['POST'])
def rent_equipment():
    data = request.json
    card_id = data.get('card_id')
    note = data.get('note')
    
    print(f"Received Rental Request: Card {card_id}, Note: {note}")

    # 1. Connect to Database A (Check if cardno exists?)
    # 2. Connect to Database B (Log the rental)
    
    # Simulate a success
    return jsonify({
        "status": "success",
        "message": "Rental logged successfully"
    })

if __name__ == '__main__':
    # Only for debug
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
