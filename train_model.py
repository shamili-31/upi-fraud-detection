import joblib
import pandas as pd
import numpy as np
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import VotingClassifier, RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

# Load dataset
data = pd.read_csv(r"C:\Users\milis\MAJOR PROJECT\synthetic_indian_upi_fraud_data.csv")
data.columns = data.columns.str.strip()

# Target and datetime
data['isFraud'] = data['FraudFlag'].apply(lambda x: 1 if x else 0)
data['Timestamp'] = pd.to_datetime(data['Timestamp'])

# Sort for time-based features
data = data.sort_values(by=['UserID', 'Timestamp'])
data['time_since_last_txn'] = data.groupby('UserID')['Timestamp'].diff().dt.total_seconds()
data['time_since_last_txn'] = data['time_since_last_txn'].fillna(999999)

# Device change count
data['device_change_count'] = 0
for user_id, group in data.groupby('UserID'):
    group = group.sort_values('Timestamp')
    counts = []
    for idx, row in group.iterrows():
        time_window_start = row['Timestamp'] - pd.Timedelta(hours=1)
        devices = group[(group['Timestamp'] >= time_window_start) & (group['Timestamp'] <= row['Timestamp'])]['DeviceID'].nunique()
        counts.append(devices)
    data.loc[group.index, 'device_change_count'] = counts

# Drop unnecessary columns
drop_cols = ['TransactionID', 'UserID', 'MerchantCategory', 'PhoneNumber', 'BankName', 'FraudFlag']
data = data.drop(columns=drop_cols)

# Log transform on Amount
data['log_amount'] = data['Amount'].apply(lambda x: np.log(x + 1))

# Normalize TransactionFrequency
data['normalized_frequency'] = data['TransactionFrequency'].str.extract('(\d+)').astype(float)
data['normalized_frequency'] /= data['normalized_frequency'].max()

# Extract hour and day
data['hour'] = data['Timestamp'].dt.hour
data['day'] = data['Timestamp'].dt.day
data = data.drop(columns=['Timestamp'])

# Encode booleans
data['unusual_location'] = data['UnusualLocation'].astype(int)
data['new_device'] = data['NewDevice'].astype(int)
data['failed_attempts_scaled'] = data['FailedAttempts'] / (data['FailedAttempts'].max() + 1)

# Drop original versions
data = data.drop(columns=['Amount', 'TransactionFrequency', 'UnusualLocation', 'NewDevice', 'FailedAttempts'])

# Separate features and target
X = data.drop('isFraud', axis=1)
y = data['isFraud']

# Sample 10% data and align X and y correctly
X_sampled = X.sample(frac=0.1, random_state=42)
y_sampled = y.loc[X_sampled.index]

# Columns
categorical_cols = ['TransactionType', 'DeviceID', 'IPAddress']
numerical_cols = [col for col in X_sampled.columns if col not in categorical_cols]

# Preprocessing
preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), numerical_cols),
        ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_cols)
    ]
)
# Classifiers
rf_model = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    min_samples_split=5,
    class_weight='balanced',
    random_state=42,
    n_jobs=-1
)
xgb_model = XGBClassifier(
    use_label_encoder=False,
    eval_metric='logloss',
    learning_rate=0.05,
    max_depth=6,
    n_estimators=100,
    scale_pos_weight=(y_sampled.value_counts()[0] / y_sampled.value_counts()[1]),
    random_state=42,
    n_jobs=-1
)

voting_clf = VotingClassifier(
    estimators=[('rf', rf_model), ('xgb', xgb_model)],
    voting='soft'
)

# Pipeline with SMOTE
pipeline = ImbPipeline(steps=[
    ('preprocessor', preprocessor),
    ('smote', SMOTE(random_state=42, sampling_strategy=0.5)),
    ('classifier', voting_clf)
])

# Train
print("\nTraining pipeline...")
pipeline.fit(X_sampled, y_sampled)

# Save
os.makedirs('models', exist_ok=True)
joblib.dump(pipeline, 'models/pipeline.pkl')
print("✅ Pipeline saved as 'models/pipeline.pkl'")

# Evaluation
y_pred = pipeline.predict(X_sampled)
print("\nClassification Report:")
print(classification_report(y_sampled, y_pred))
print("Accuracy:", accuracy_score(y_sampled, y_pred))

