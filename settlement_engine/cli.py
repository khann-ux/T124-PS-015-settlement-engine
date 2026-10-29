import csv
import os
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional
from settlement_engine.models.merchant import Merchant, RiskGrade, MDRPlan, BankAccount
from settlement_engine.models.transaction import EventType, LifecycleEvent
from settlement_engine.engine import SettlementEngine
from settlement_engine.rules.invoice_generator import InvoiceGenerator


def parse_date(date_str: str) -> date:
    return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()


def parse_datetime(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str.strip())


class SettlementCLI:
    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = output_dir
        self.engine = SettlementEngine()
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "payouts"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "invoices"), exist_ok=True)

    def load_merchants(self, filepath: str) -> int:
        count = 0
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                neg_rate = None
                if row.get("negotiated_rate") and row["negotiated_rate"].strip():
                    neg_rate = Decimal(row["negotiated_rate"].strip())

                bank = BankAccount(
                    account_number=row.get("account_num", "1000000001"),
                    ifsc_code=row.get("ifsc", "HDFC0001234"),
                    bank_name=row.get("bank_name", "HDFC Bank"),
                    account_holder=row.get("account_holder", row["business_name"]),
                )

                risk = RiskGrade(row["risk_grade"].strip().upper())
                plan = MDRPlan(row["mdr_plan"].strip().upper())

                m = Merchant(
                    merchant_id=row["merchant_id"].strip(),
                    business_name=row["business_name"].strip(),
                    mcc=row["mcc"].strip(),
                    base_risk_grade=risk,
                    current_risk_grade=risk,
                    mdr_plan=plan,
                    bank_account=bank,
                    gstin=row.get("gstin", "").strip() or None,
                    negotiated_rate=neg_rate,
                )
                self.engine.register_merchant(m)
                count += 1
        return count

    def load_holidays(self, filepath: str) -> int:
        count = 0
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                h_date = parse_date(row["date"])
                self.engine.register_holiday(h_date)
                count += 1
        return count

    def load_and_process_events(self, filepath: str) -> int:
        count = 0
        events = []
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rep_won = None
                if row.get("representment_won") is not None and row["representment_won"].strip() != "":
                    val = row["representment_won"].strip().lower()
                    rep_won = val in ("true", "1", "yes")

                ev = LifecycleEvent(
                    event_id=row["event_id"].strip(),
                    txn_id=row["txn_id"].strip(),
                    merchant_id=row["merchant_id"].strip(),
                    event_type=EventType(row["event_type"].strip().upper()),
                    amount=Decimal(row["amount"].strip()),
                    timestamp=parse_datetime(row["timestamp"]),
                    representment_success=rep_won,
                    notes=row.get("instrument_or_notes", "").strip() or None,
                )
                events.append(ev)

        events.sort(key=lambda e: e.timestamp)
        for ev in events:
            self.engine.process_event(ev)
            count += 1
        return count

    def run_settlement_range(self, start_date: date, end_date: date) -> int:
        current = start_date
        total_days = 0
        while current <= end_date:
            batch = self.engine.run_daily_settlement(current)
            self._export_daily_payout(batch)
            current += timedelta(days=1)
            total_days += 1
        return total_days

    def export_mdr_transactions(self) -> str:
        filepath = os.path.join(self.output_dir, "mdr_transactions.csv")
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "txn_id", "merchant_id", "instrument", "authorized_amount",
                "captured_amount", "capture_timestamp", "mdr_amount",
                "gst_amount", "net_amount", "settlement_date", "state"
            ])
            for txn in self.engine.captured_transactions:
                writer.writerow([
                    txn.txn_id,
                    txn.merchant_id,
                    txn.instrument.value,
                    f"{txn.authorized_amount:.2f}",
                    f"{txn.captured_amount:.2f}",
                    txn.capture_timestamp.isoformat() if txn.capture_timestamp else "",
                    f"{txn.mdr_amount:.2f}",
                    f"{txn.gst_amount:.2f}",
                    f"{txn.net_captured_amount:.2f}",
                    txn.settlement_date.strftime("%Y-%m-%d") if txn.settlement_date else "",
                    txn.state.value,
                ])
        return filepath

    def _export_daily_payout(self, batch) -> None:
        if not batch.payout_records:
            return
        filename = f"payout_{batch.batch_date.strftime('%Y-%m-%d')}.csv"
        filepath = os.path.join(self.output_dir, "payouts", filename)
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "settlement_date", "merchant_id", "gross_captured", "total_mdr",
                "total_gst", "net_captured", "total_refunds", "chargeback_debits",
                "representment_credits", "net_chargebacks", "reserve_withheld",
                "reserve_released", "opening_balance", "calculated_settlement",
                "actual_payout", "closing_balance", "status", "aging_override", "notes"
            ])
            for p in batch.payout_records:
                writer.writerow([
                    p.settlement_date.strftime("%Y-%m-%d"),
                    p.merchant_id,
                    f"{p.gross_captured:.2f}",
                    f"{p.total_mdr:.2f}",
                    f"{p.total_gst:.2f}",
                    f"{p.net_captured:.2f}",
                    f"{p.total_refunds:.2f}",
                    f"{p.total_chargeback_debits:.2f}",
                    f"{p.total_representment_credits:.2f}",
                    f"{p.net_chargebacks:.2f}",
                    f"{p.reserve_withheld:.2f}",
                    f"{p.reserve_released:.2f}",
                    f"{p.opening_balance:.2f}",
                    f"{p.calculated_settlement:.2f}",
                    f"{p.actual_payout:.2f}",
                    f"{p.closing_balance:.2f}",
                    p.payout_status,
                    "YES" if p.aging_override_applied else "NO",
                    p.note,
                ])

    def export_invoices(self, year: int, month: int) -> None:
        invoices = self.engine.generate_monthly_invoices(year, month)
        summary_path = os.path.join(self.output_dir, "invoices", f"summary_{year:04d}_{month:02d}.csv")
        with open(summary_path, mode="w", newline="", encoding="utf-8") as sf:
            swriter = csv.writer(sf)
            swriter.writerow([
                "invoice_number", "billing_period", "merchant_id", "business_name",
                "gstin", "is_gst_registered", "total_txns", "gross_volume",
                "total_mdr", "total_gst", "grand_total", "itc_eligible"
            ])
            for inv in invoices:
                swriter.writerow([
                    inv.invoice_number,
                    inv.billing_period,
                    inv.merchant_id,
                    inv.business_name,
                    inv.gstin or "",
                    "YES" if inv.is_gst_registered else "NO",
                    inv.total_transactions,
                    f"{inv.total_gross_volume:.2f}",
                    f"{inv.total_mdr:.2f}",
                    f"{inv.total_gst:.2f}",
                    f"{inv.grand_total:.2f}",
                    "YES" if inv.itc_eligible else "NO",
                ])

                inv_filename = f"{inv.invoice_number}.txt"
                inv_filepath = os.path.join(self.output_dir, "invoices", inv_filename)
                with open(inv_filepath, mode="w", encoding="utf-8") as inf:
                    inf.write(InvoiceGenerator.format_invoice_text(inv))

    def export_rejections(self) -> str:
        filepath = os.path.join(self.output_dir, "rejected_events.csv")
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["event_id", "txn_id", "merchant_id", "event_type", "error_code", "error_message", "timestamp"])
            for r in self.engine.rejection_log:
                writer.writerow([
                    r["event_id"], r["txn_id"], r["merchant_id"],
                    r["event_type"], r["error_code"], r["error_message"], r["timestamp"]
                ])
        return filepath
