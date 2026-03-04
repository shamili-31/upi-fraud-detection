from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import requests
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import re
from models import db, bcrypt, User, Transaction
from config import Config

# Initialize the app
app = Flask(__name__)
app.secret_key = '1766a66e868802dda4f190ad04f0f1d5871f3ae7eccb2378'
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
bcrypt.init_app(app)

# Login manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Load trained pipeline
pipeline = joblib.load('models/pipeline.pkl')

def check_new_device():
    return 0

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('❌ Username already exists. Please choose a different one.', 'error')
            return redirect(url_for('register'))

        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('❌ Email already registered. Please use a different email.', 'error')
            return redirect(url_for('register'))

        if (len(password) < 8 or
            not re.search(r'[A-Z]', password) or
            not re.search(r'[a-z]', password) or
            not re.search(r'\d', password) or
            not re.search(r'[!@#$%^&*(),.?]', password)):
            flash('❌ Password must be at least 8 characters and include uppercase, lowercase, digit, and special character.', 'error')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('✅ Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

RECAPTCHA_SECRET_KEY = '6LeadlQrAAAAAGB-hV_DkFSdcYtBd5SyUkZnMeER'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        recaptcha_response = request.form.get('g-recaptcha-response')

        data = {'secret': RECAPTCHA_SECRET_KEY, 'response': recaptcha_response}
        r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
        result = r.json()

        if not result.get('success'):
            flash('reCAPTCHA verification failed. Please try again.', 'danger')
            return render_template('login.html')
            
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))

        flash('Login failed. Check your email and/or password', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    total_transactions = Transaction.query.count()
    total_frauds = Transaction.query.filter_by(prediction=1).count()
    active_users = db.session.query(Transaction.user_id).distinct().count()

    return render_template(
        'dashboard.html',
        total_transactions=total_transactions,
        total_frauds=total_frauds,
        active_users=active_users
    )

@app.route('/predict', methods=['GET', 'POST'])
@login_required
def predict_page():
    prediction = None
    if request.method == 'POST':
        try:
            amount = float(request.form['Amount'])
            transaction_type = request.form['TransactionType']
            failed_attempts = int(request.form['FailedAttempts'])

            avg_transaction_amount = 1500
            transaction_frequency = 10
            unusual_location = 0
            new_device = check_new_device()
            ip_address = request.remote_addr
            latitude = 12.9716
            longitude = 77.5946
            device_id = 'device_xyz'
            device_change_count = 1
            time_since_last_txn = 300
            timestamp = datetime.now()
            hour = timestamp.hour
            day = timestamp.day

            log_amount = np.log1p(amount)
            failed_attempts_scaled = failed_attempts / 6
            normalized_frequency = transaction_frequency / 30.0
            unusual_amount = 1 if amount > avg_transaction_amount * 2 else 0

            input_dict = {
                'TransactionType': transaction_type,
                'DeviceID': device_id,
                'IPAddress': ip_address,
                'Latitude': latitude,
                'Longitude': longitude,
                'AvgTransactionAmount': avg_transaction_amount,
                'log_amount': log_amount,
                'normalized_frequency': normalized_frequency,
                'unusual_location': unusual_location,
                'UnusualAmount': unusual_amount,
                'new_device': new_device,
                'failed_attempts_scaled': failed_attempts_scaled,
                'device_change_count': device_change_count,
                'time_since_last_txn': time_since_last_txn,
                'hour': hour,
                'day': day
            }
            input_df = pd.DataFrame([input_dict])

            prediction_prob = pipeline.predict_proba(input_df)[:, 1][0]
            threshold = 0.7
            prediction = 1 if prediction_prob > threshold else 0

            new_transaction = Transaction(
                user_id=current_user.id,
                amount=amount,
                transaction_type=transaction_type,
                failed_attempts=failed_attempts,
                prediction=prediction
            )
            db.session.add(new_transaction)
            db.session.commit()

        except Exception as e:
            print("Error in prediction:", e)
            prediction = None

    return render_template('predict.html', prediction=prediction)

@app.route('/update_contact_info', methods=['POST'])
@login_required
def update_contact_info():
    email = request.form.get('email')
    phone = request.form.get('phone')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not bcrypt.check_password_hash(current_user.password, current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for('predict'))

    current_user.email = email
    current_user.phone = phone
    if new_password:
        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return redirect(url_for('predict'))
        current_user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')

    db.session.commit()
    flash("Contact information updated successfully.", "success")
    return redirect(url_for('predict'))

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user = current_user
    db.session.delete(user)
    db.session.commit()
    logout_user()
    flash('Your account has been deleted successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/api/transaction-stats')
@login_required
def transaction_stats():
    stats = (
        db.session.query(
            db.func.date(Transaction.transaction_date).label('date'),
            db.func.count(Transaction.id).label('count')
        )
        .filter(Transaction.user_id == current_user.id)
        .group_by('date')
        .order_by('date')
        .all()
    )
    data = [{'date': str(date), 'count': count} for date, count in stats]
    return jsonify(data)

@app.route('/analyze', methods=['POST'])
@login_required
def analyze_qr():
    data = request.get_json()
    upi_url = data.get('upi_string', '')
    result = check_qr_safety(upi_url)
    return jsonify({'result': result})

def check_qr_safety(upi_url):
    try:
        parsed_url = urlparse(upi_url)
        query_params = parse_qs(parsed_url.query)
        upi_id = query_params.get('pa', [''])[0]
        name = query_params.get('pn', [''])[0].lower()
        amount = float(query_params.get('am', [0])[0])

        suspicious_keywords = ['refund', 'lottery', 'kyc', 'govt', 'admin']

        if amount > 10000:
            return f"⚠️ Suspicious! Amount requested: ₹{amount}"
        if any(word in name for word in suspicious_keywords):
            return f"⚠️ Suspicious name: '{name}'"
        if 'pay' in parsed_url.path:
            return f"⚠️ QR is for requesting payment, not receiving."

        return "✅ This QR code looks safe."

    except Exception as e:
        return f"Error analyzing QR: {str(e)}"

@app.route('/bulk_predict', methods=['POST'])
@login_required
def bulk_predict():
    if 'file' not in request.files or request.files['file'].filename == '':
        flash('⚠️ No file selected.', 'warning')
        return redirect(url_for('bulk_upload_page'))

    file = request.files['file']
    try:
        df = pd.read_csv(file)
        required_columns = ['Amount', 'TransactionType', 'FailedAttempts', 'AvgTransactionAmount', 'TransactionFrequency', 'Timestamp']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            flash(f"⚠️ Missing columns in CSV: {', '.join(missing_columns)}", 'danger')
            return redirect(url_for('bulk_upload_page'))

        for col, default in [('Amount', 0), ('AvgTransactionAmount', 0), ('FailedAttempts', 0), ('TransactionFrequency', 10)]:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(default)

        df['log_amount'] = np.log1p(df['Amount'])
        df['failed_attempts_scaled'] = df['FailedAttempts'] / 6
        df['normalized_frequency'] = df['TransactionFrequency'] / 30.0
        df['unusual_location'] = 0
        df['new_device'] = 0
        df['unusual_amount'] = (df['Amount'] > 2 * df['AvgTransactionAmount']).astype(int)
        df['device_change_count'] = 1
        df['time_since_last_txn'] = 300

        df['hour'] = pd.to_datetime(df['Timestamp'], errors='coerce').dt.hour.fillna(0).astype(int)
        df['day'] = pd.to_datetime(df['Timestamp'], errors='coerce').dt.day.fillna(1).astype(int)

        probs = pipeline.predict_proba(df)[:, 1]
        threshold = 0.6
        predictions = (probs >= threshold).astype(int)
        df['FraudPrediction'] = ['Fraud' if p == 1 else 'Not Fraud' for p in predictions]

        display_columns = ['TransactionType', 'Amount', 'FailedAttempts', 'FraudPrediction']
        table_html = df[display_columns].head(100).to_html(classes='table table-bordered table-hover', index=False)

        fraud_count = sum(predictions)
        not_fraud_count = len(df) - fraud_count
        fraud_percent = round(100 * fraud_count / len(df), 2)

        return render_template(
           'bulk_upload.html',
            bulk_predictions=table_html,
            total_rows=len(df),
            fraud_count=fraud_count,
            not_fraud_count=not_fraud_count,
            fraud_percent=fraud_percent
        )

    except Exception as e:
        print(f"Error in bulk_predict: {e}")
        flash(f"❌ Error processing file: {str(e)}", 'danger')
        return redirect(url_for('bulk_upload_page'))

@app.route('/bulk-upload')
@login_required
def bulk_upload_page():
    return render_template('bulk_upload.html')
    
@app.route('/qr-tools')
@login_required
def qr_tools_page():
    return render_template('qr_scan.html')

if __name__ == '__main__':
    app.run(debug=True)
