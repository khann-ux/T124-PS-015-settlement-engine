"""
Master CLI Entrypoint for Payment Aggregator Settlement Engine (PS-015).
Runs simulation over input data files and generates daily payouts, MDR reports, and invoices.
"""

import argparse
import sys
from datetime import datetime
from settlement_engine.cli import SettlementCLI, parse_date


def main():
    parser = argparse.ArgumentParser(
        description="PS-015: Payment Aggregator Merchant Settlement Engine with MDR, Holdbacks and Refund Netting"
    )
    parser.add_argument("--merchants", default="data/merchants.csv", help="Path to merchants CSV file")
    parser.add_argument("--holidays", default="data/holidays.csv", help="Path to bank holidays CSV file")
    parser.add_argument("--events", default="data/events.csv", help="Path to lifecycle events CSV file")
    parser.add_argument("--start-date", default="2026-09-01", help="Settlement start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2026-10-15", help="Settlement end date (YYYY-MM-DD)")
    parser.add_argument("--invoice-year", type=int, default=2026, help="Invoice billing year")
    parser.add_argument("--invoice-month", type=int, default=9, help="Invoice billing month")
    parser.add_argument("--output-dir", default="outputs", help="Directory to save generated outputs")

    args = parser.parse_args()

    print("=" * 80)
    print("  PAYMENT AGGREGATOR MERCHANT SETTLEMENT ENGINE (PS-015)")
    print("  Domain: BFSI — Merchant Settlements & Clearing")
    print("=" * 80)

    cli = SettlementCLI(output_dir=args.output_dir)

    print(f"\n[1/5] Ingesting Merchants from {args.merchants}...")
    num_merchants = cli.load_merchants(args.merchants)
    print(f"      Successfully registered {num_merchants} merchants.")

    print(f"\n[2/5] Ingesting Bank Holidays from {args.holidays}...")
    num_holidays = cli.load_holidays(args.holidays)
    print(f"      Successfully registered {num_holidays} declared holidays.")

    print(f"\n[3/5] Streaming Transaction Lifecycle Events from {args.events}...")
    num_events = cli.load_and_process_events(args.events)
    print(f"      Processed {num_events} lifecycle events.")
    print(f"      Successful captures: {len(cli.engine.captured_transactions)}")
    print(f"      Rejected illegal events: {len(cli.engine.rejection_log)}")

    s_date = parse_date(args.start_date)
    e_date = parse_date(args.end_date)
    print(f"\n[4/5] Running Daily Settlement Batch Jobs from {s_date} to {e_date}...")
    days_run = cli.run_settlement_range(s_date, e_date)
    print(f"      Completed {days_run} daily settlement cycles.")

    print(f"\n[5/5] Generating Monthly Invoices for Billing Period {args.invoice_year}-{args.invoice_month:02d}...")
    cli.export_invoices(args.invoice_year, args.invoice_month)
    
    # Export transaction MDR and rejection logs
    mdr_file = cli.export_mdr_transactions()
    rej_file = cli.export_rejections()

    print("\n" + "=" * 80)
    print("  SIMULATION COMPLETED SUCCESSFULLY!")
    print(f"  Outputs generated in: {args.output_dir}/")
    print(f"  - Per-transaction MDR audit:  {mdr_file}")
    print(f"  - Rejected events log:        {rej_file}")
    print(f"  - Daily Payout files:         {args.output_dir}/payouts/payout_YYYY-MM-DD.csv")
    print(f"  - Monthly Invoices:           {args.output_dir}/invoices/")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
