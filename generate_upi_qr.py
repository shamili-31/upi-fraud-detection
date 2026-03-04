import qrcode

def generate_upi_qr(pa, pn, am, tn, filename):
    upi_url = f"upi://pay?pa={pa}&pn={pn}&am={am}&cu=INR&tn={tn}"
    print(f"Generating QR for: {upi_url}")
    
    qr = qrcode.make(upi_url)
    qr.save(filename)
    print(f"Saved QR code to {filename}")

samples = [
    ("merchant@bank", "Safe Shop", "100.00", "Payment for order", "safe_100.png"),
    ("scammer@bank", "Refund Dept", "50000.00", "Urgent refund", "suspicious_refund.png"),
    ("lottery@bank", "Lottery Winner", "1000.00", "Prize payout", "suspicious_lottery.png"),
    ("govt@bank", "Govt Admin", "15000.00", "Tax payment", "suspicious_govt.png"),
    ("friend@bank", "Friend", "250.00", "Lunch split", "safe_friend.png"),
]

for pa, pn, am, tn, filename in samples:
    generate_upi_qr(pa, pn, am, tn, filename)
