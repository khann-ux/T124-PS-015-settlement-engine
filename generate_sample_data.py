import csv
import os
from datetime import datetime, timedelta
from decimal import Decimal

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def generate_merchants():
    merchants = [
        ["M001", "Apex Retail Supermarket", "5411", "LOW", "STANDARD", "", "27AAACA1234A1Z5", "91001002345678", "HDFC0000128", "HDFC Bank", "Apex Retail Pvt Ltd"],
        ["M002", "Nova Electronics Store", "5732", "LOW", "FLAT_PLAN", "", "29AABCN5678B1Z2", "02450500123456", "ICIC0000245", "ICICI Bank", "Nova Electronics LLP"],
        ["M003", "CloudNine Travel & Hotels", "4722", "MEDIUM", "STANDARD", "", "07AAACC9988D1Z9", "30987654321012", "SBIN0001456", "State Bank of India", "CloudNine Travel Corp"],
        ["M004", "Saffron Artisans & Crafts", "5947", "MEDIUM", "NEGOTIATED", "0.0120", "", "11223344556677", "KKBK0000890", "Kotak Mahindra Bank", "Saffron Handloom"],
        ["M005", "Vanguard Crypto & Gaming", "7995", "HIGH", "STANDARD", "", "33AAACV4455E1Z8", "50100234567890", "HDFC0000501", "HDFC Bank", "Vanguard Gaming Tech"],
        ["M006", "Global Forex & Escrow", "6051", "HIGH", "FLAT_PLAN", "", "", "60123456789012", "UTIB0000601", "Axis Bank", "Global Forex Services"],
        ["M007", "MicroBite Chai & Snacks", "5814", "LOW", "STANDARD", "", "27AAACM1122F1Z1", "70123456789012", "PUNB0000701", "Punjab National Bank", "MicroBite Express"],
        ["M008", "UrbanStyle Fashion Boutique", "5651", "LOW", "STANDARD", "", "27AAACU3344G1Z3", "80123456789012", "BARB0000801", "Bank of Baroda", "UrbanStyle Fashion"],
    ]

    filepath = os.path.join(DATA_DIR, "merchants.csv")
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "merchant_id", "business_name", "mcc", "risk_grade", "mdr_plan",
            "negotiated_rate", "gstin", "account_num", "ifsc", "bank_name", "account_holder"
        ])
        writer.writerows(merchants)
    print(f"Generated {filepath}")


def generate_holidays():
    holidays = [
        ["2026-09-04", "Janmashtami"],
        ["2026-09-16", "Eid-e-Milad"],
        ["2026-10-02", "Mahatma Gandhi Jayanti"],
        ["2026-10-20", "Dussehra / Vijayadashami"],
    ]
    filepath = os.path.join(DATA_DIR, "holidays.csv")
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "description"])
        writer.writerows(holidays)
    print(f"Generated {filepath}")


def generate_events():
    instruments = ["UPI", "DEBIT_CARD", "CREDIT_CARD", "NET_BANKING", "WALLET", "INTERNATIONAL_CARD"]
    start_dt = datetime(2026, 9, 1, 9, 0, 0)
    events = []
    event_idx = 1
    txn_idx = 1000

    for day in range(45):
        current_date = start_dt + timedelta(days=day)

        for m_id in ["M001", "M002", "M003", "M004", "M005", "M006"]:
            for tx_num in range(2):
                txn_idx += 1
                t_id = f"TXN-{txn_idx}"
                inst = instruments[(day + tx_num + int(m_id[-1])) % len(instruments)]

                if inst == "UPI":
                    amount = Decimal("1500.00") if day % 2 == 0 else Decimal("2000.01")
                elif inst == "DEBIT_CARD":
                    amount = Decimal("1800.00") if day % 2 == 0 else Decimal("4500.00")
                elif inst == "INTERNATIONAL_CARD":
                    amount = Decimal("8200.00")
                else:
                    amount = Decimal("3200.00") + Decimal(day * 50)

                auth_time = current_date.replace(hour=10 + (tx_num * 2), minute=15)
                events.append([
                    f"EV-{event_idx:04d}", t_id, m_id, "AUTH", f"{amount:.2f}",
                    auth_time.isoformat(), inst, ""
                ])
                event_idx += 1

                if day == 5 and tx_num == 0:
                    cap_time = current_date.replace(hour=23, minute=0, second=0)
                elif day == 5 and tx_num == 1:
                    cap_time = current_date.replace(hour=23, minute=0, second=1)
                else:
                    cap_time = current_date.replace(hour=14 + (tx_num * 2), minute=30)

                events.append([
                    f"EV-{event_idx:04d}", t_id, m_id, "CAPTURE", f"{amount:.2f}",
                    cap_time.isoformat(), inst, ""
                ])
                event_idx += 1

                if day in (8, 15, 22, 28) and tx_num == 0:
                    ref_time = cap_time + timedelta(days=3, hours=2)
                    ref_amount = Decimal("500.00")
                    events.append([
                        f"EV-{event_idx:04d}", t_id, m_id, "REFUND", f"{ref_amount:.2f}",
                        ref_time.isoformat(), inst, ""
                    ])
                    event_idx += 1

                if day in (10, 20) and tx_num == 1 and m_id in ("M003", "M005"):
                    cb_time = cap_time + timedelta(days=4)
                    events.append([
                        f"EV-{event_idx:04d}", t_id, m_id, "CHARGEBACK", f"{amount:.2f}",
                        cb_time.isoformat(), inst, ""
                    ])
                    event_idx += 1

                    rep_time = cb_time + timedelta(days=5)
                    rep_won = "true" if m_id == "M003" else "false"
                    events.append([
                        f"EV-{event_idx:04d}", t_id, m_id, "REPRESENTMENT", f"{amount:.2f}",
                        rep_time.isoformat(), inst, rep_won
                    ])
                    event_idx += 1

    m007_auth = start_dt.replace(day=2, hour=11, minute=0)
    m007_cap = start_dt.replace(day=2, hour=11, minute=30)
    events.append([
        f"EV-{event_idx:04d}", "TXN-M007-001", "M007", "AUTH", "99.99",
        m007_auth.isoformat(), "UPI", ""
    ])
    event_idx += 1
    events.append([
        f"EV-{event_idx:04d}", "TXN-M007-001", "M007", "CAPTURE", "99.99",
        m007_cap.isoformat(), "UPI", ""
    ])
    event_idx += 1

    for i in range(5):
        txn_idx += 1
        t_id = f"TXN-M008-{i+1:03d}"
        ev_t = start_dt + timedelta(days=2, hours=i)
        events.append([
            f"EV-{event_idx:04d}", t_id, "M008", "AUTH", "2500.00",
            ev_t.isoformat(), "CREDIT_CARD", ""
        ])
        event_idx += 1
        events.append([
            f"EV-{event_idx:04d}", t_id, "M008", "CAPTURE", "2500.00",
            (ev_t + timedelta(minutes=15)).isoformat(), "CREDIT_CARD", ""
        ])
        event_idx += 1

    cb_m008_time = start_dt + timedelta(days=6, hours=12)
    events.append([
        f"EV-{event_idx:04d}", "TXN-M008-001", "M008", "CHARGEBACK", "2500.00",
        cb_m008_time.isoformat(), "CREDIT_CARD", ""
    ])
    event_idx += 1

    valid_d7_auth = start_dt.replace(day=5, hour=9, minute=0)
    valid_d7_cap = valid_d7_auth + timedelta(days=7, hours=0)
    events.append([
        f"EV-{event_idx:04d}", "TXN-EDGE-D7-VALID", "M001", "AUTH", "3000.00",
        valid_d7_auth.isoformat(), "UPI", ""
    ])
    event_idx += 1
    events.append([
        f"EV-{event_idx:04d}", "TXN-EDGE-D7-VALID", "M001", "CAPTURE", "3000.00",
        valid_d7_cap.isoformat(), "UPI", ""
    ])
    event_idx += 1

    exp_auth = start_dt.replace(day=1, hour=9, minute=0)
    exp_cap = exp_auth + timedelta(days=7, hours=1)
    events.append([
        f"EV-{event_idx:04d}", "TXN-EDGE-EXPIRED", "M001", "AUTH", "1000.00",
        exp_auth.isoformat(), "UPI", ""
    ])
    event_idx += 1
    events.append([
        f"EV-{event_idx:04d}", "TXN-EDGE-EXPIRED", "M001", "CAPTURE", "1000.00",
        exp_cap.isoformat(), "UPI", ""
    ])
    event_idx += 1

    illegal_auth = start_dt.replace(day=3, hour=10, minute=0)
    illegal_ref = start_dt.replace(day=3, hour=11, minute=0)
    events.append([
        f"EV-{event_idx:04d}", "TXN-EDGE-ILLEGAL-REF", "M002", "AUTH", "2000.00",
        illegal_auth.isoformat(), "UPI", ""
    ])
    event_idx += 1
    events.append([
        f"EV-{event_idx:04d}", "TXN-EDGE-ILLEGAL-REF", "M002", "REFUND", "500.00",
        illegal_ref.isoformat(), "UPI", ""
    ])
    event_idx += 1

    events.sort(key=lambda x: x[5])

    filepath = os.path.join(DATA_DIR, "events.csv")
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "event_id", "txn_id", "merchant_id", "event_type", "amount",
            "timestamp", "instrument_or_notes", "representment_won"
        ])
        writer.writerows(events)
    print(f"Generated {filepath} with {len(events)} events.")


if __name__ == "__main__":
    generate_merchants()
    generate_holidays()
    generate_events()
