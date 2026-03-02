from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os, logging

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))

# Create database
os.makedirs(f'{basedir}/data', exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data', 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# 1. User database
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.String(50), unique=True, nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    name = db.Column(db.String(100), nullable=True) 
    
    # Enables back-referencing to rental transactions for this user
    rentals = db.relationship('RentalTransaction', backref='user', lazy=True)

# 2. Equipment database
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    extra_info = db.Column(db.Text, nullable=True)
    is_rented = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(50), nullable=True)
    
    # Enables back-referencing to rental transactions for this item
    history = db.relationship('RentalTransaction', backref='item', lazy=True)

    @property
    def current_renter_email(self):
        if not self.is_rented:
            return None
        # Kig i historikken for at finde det udlån, der ikke er afleveret endnu
        for transaction in self.history:
            if transaction.returned_at is None:
                # Retur emailen på den bruger, der sidder med udstyret
                return transaction.user.email
        return "Unknown"

# 3. Rental log database
class RentalTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    
    # Timestamps
    rented_at = db.Column(db.DateTime, default=datetime.now)
    returned_at = db.Column(db.DateTime, nullable=True) # Tom indtil udstyret afleveres!


with app.app_context():
    db.create_all()


log_file_path = os.path.join(basedir, 'data', 'app.log')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)

# Serve the HTML file
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/inventory')
def inventory():
    items = Item.query.all()
    return render_template('inventory.html', items=items)


@app.route('/logs')
def logs():
    transactions = RentalTransaction.query.order_by(RentalTransaction.rented_at.desc()).all()
    return render_template('logs.html', transactions=transactions)


@app.route('/api/check_user', methods=['POST'])
def check_user():
    data = request.json
    card_id = data.get('card_id')
    email = data.get('email')

    user = None
    if card_id:
        user = User.query.filter_by(card_id=card_id).first()
    elif email:
        user = User.query.filter_by(email=email).first()

    if user:
        return jsonify({"exists": True, "name": user.name, "email": user.email})
    else:
        return jsonify({"exists": False})


# The API Endpoint for handling rentals and returns
@app.route('/api/transaction', methods=['POST'])
def rent_equipment():
    try:
        data = request.json
        card_id = data.get('card_id')
        currentEmail = data.get('email')
        currentName = data.get('name', "Unknown User")
        note = data.get('note')
        action = data.get('action') 
        
        logging.info(f"Received Rental Request: Card {card_id}, Note: {note}, Action: {action}")

        if card_id:
            user = User.query.filter_by(card_id=card_id).first()
        elif currentEmail:
            user = User.query.filter_by(email=currentEmail).first()

        if not user:
            logging.info(f"Card ID {card_id} not found in database. Creating new user entry.")
            new_user = User(card_id=card_id, email=currentEmail, name=currentName)
            db.session.add(new_user)
            db.session.commit()

            user = new_user

        barcodes = [b.strip() for b in note.split(',') if b.strip()]
        
        # add items to rental log
        for barcode in barcodes:
            item = Item.query.filter_by(barcode=barcode).first()

            if not item:
                logging.warning(f"Item with barcode {barcode} not found.")
                return jsonify({
                    "status": "error",
                    "message": f"Item with barcode {barcode} not found."
                }), 404
            
            if action == 'rent':
                item.is_rented = True
                
                new_transaction = RentalTransaction(
                    user_id=user.id,
                    item_id=item.id,
                    rented_at=datetime.now()
                )
                db.session.add(new_transaction)

            elif action == 'return':
                item.is_rented = False
                
                open_transaction = RentalTransaction.query.filter_by(
                    user_id=user.id, 
                    item_id=item.id, 
                    returned_at=None
                ).first()
                
                if open_transaction:
                    open_transaction.returned_at = datetime.now()
                else:
                    logging.warning(f"No open rental transaction found for user {user.card_id} and item {item.barcode}.")
                    return jsonify({
                        "status": "error",
                        "message": f"No open rental transaction found for user {user.card_id} and item {item.barcode}."
                    }), 404

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Transaction logged successfully"
        })
    
    except Exception as e:
        logging.error(f"Error processing transaction: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"From python: {str(e)}"
        }), 500




if __name__ == '__main__':
    # Only for debug
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
