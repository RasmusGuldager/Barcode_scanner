from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))

# Create database
os.makedirs(f'{basedir}/data', exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data', 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=True) 


class Rental(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.String(50), nullable=False)
    items_rented = db.Column(db.String(200), nullable=False)


with app.app_context():
    db.create_all()


# Serve the HTML file
@app.route('/')
def home():
    return render_template('index.html')

# The API Endpoint JS calls
@app.route('/api/rent', methods=['POST'])
def rent_equipment():
    data = request.json
    card_id = data.get('card_id')
    note = data.get('note')
    
    print(f"Received Rental Request: Card {card_id}, Note: {note}")

    user = User.query.filter_by(card_id=card_id).first()

    if not user:
        print(f"No user found with card ID {card_id}. Creating new user.")
        new_user = User(card_id=card_id, name="Uknown User")
        db.session.add(new_user)
        db.session.commit()
    
    # add items to rental log
    new_rental = Rental(card_id=card_id, items_rented=note)
    db.session.add(new_rental)
    db.session.commit()
    
    # Simulate a success
    return jsonify({
        "status": "success",
        "message": "Rental logged successfully"
    })

if __name__ == '__main__':
    # Only for debug
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
