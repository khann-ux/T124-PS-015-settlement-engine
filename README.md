# T124-PS-015: Payment Aggregator Merchant Settlement Engine

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-42%20Passed-brightgreen.svg)]()
[![Domain](https://img.shields.io/badge/Domain-BFSI%20Payments-orange.svg)]()
[![Precision](https://img.shields.io/badge/Precision-Arbitrary%20Decimal-purple.svg)]()

> **PS-015**: Payment Aggregator Merchant Settlement with MDR, Holdbacks, and Refund Netting.  
> Production-grade, command-file driven financial settlement engine engineered with zero-float arbitrary precision, multi-tiered rolling reserves, dynamic risk mitigation, and full tax/ITC compliance.

---

## 🌟 Key Features & Capabilities

- **Zero-Float Financial Engine**: Uses `decimal.Decimal` with standard `ROUND_HALF_UP` banking rounding to eliminate rounding drift across ledgers.
- **MDR & GST Matrix (BR-01, BR-02)**: Complete rate matrix for UPI, Debit Card, Credit Card, Net Banking, Wallet, and International Cards, supporting Flat Plans and Merchant-Negotiated rates.
- **Strict Lifecycle FSM (BR-03, BR-11)**: State machine validating `AUTH -> CAPTURE (full/partial) -> REFUND(s) -> CHARGEBACK -> REPRESENTMENT`, with a 7-day auth expiry rule.
- **Business Calendar & Cut-off (BR-04)**: T+1 (LOW), T+2 (MEDIUM), T+3 (HIGH) business day settlement cycles with a 23:00:00 cut-off boundary, skipping weekends and declared bank holidays.
- **Refund Netting & Retained MDR (BR-05)**: 180-day refund window with full MDR retention (BFSI standard practice).
- **Chargeback Debits & Representment (BR-06)**: ₹250 penalty fee debits; representment credits back principal transaction amounts upon success.
- **Risk-Based Rolling Reserves (BR-07)**: Automated holdbacks (HIGH: 10% for 90 days; MEDIUM: 5% for 45 days; LOW: 0%) with holiday rollover releases.
- **Negative Balance & 30-Day Aging (BR-08)**: Deficit carry-forward with ₹0 disbursement; negative balances block reserve releases; 30-day aging override for amounts below ₹100.
- **Dynamic Risk Downgrades (BR-09)**: Trailing 30-day chargeback ratio monitoring (> 1.00% triggers next-day tier downgrade; 60 clean days recovery).
- **Monthly MDR & GST Invoicing (BR-10)**: Generated on the 1st of the month, formatting itemized GST with ITC claims for registered merchants vs non-ITC lines for unregistered merchants.
- **Extra-Credit Stretch Goals**: Marketplace Split Settlement with commission netting & Instant Same-Day Payouts with daily limits and 0.10% fees.

---

## 📁 Repository Structure

```
T124-PS-015/
├── run.py                              # Master CLI entrypoint
├── generate_sample_data.py             # Generates sample merchants, calendar & 1000+ events
├── requirements.txt                    # Minimal dependencies (pytest)
├── settlement_engine/
│   ├── engine.py                       # Master Settlement Orchestrator
│   ├── cli.py                          # Command file reader and CSV/invoice exporter
│   ├── models/
│   │   ├── merchant.py                 # Merchant, RiskGrade, MDRPlan, BankAccount
│   │   ├── transaction.py              # PaymentInstrument, Transaction, LifecycleEvent
│   │   ├── holiday.py                  # CalendarService, Business days, Holiday rolling
│   │   ├── settlement.py               # DailySettlementBatch, PayoutRecord, ReserveEntry
│   │   └── invoice.py                  # MonthlyInvoice, InvoiceLineItem
│   └── rules/
│       ├── mdr_calculator.py           # BR-01, BR-02 (MDR & GST Engine)
│       ├── lifecycle_validator.py      # BR-03, BR-11 (FSM Transitions & 7-day Expiry)
│       ├── calendar_service.py         # BR-04 (T+N Cycles & 23:00 Cut-off)
│       ├── refund_engine.py            # BR-05 (Refund Netting & 180-day window)
│       ├── chargeback_engine.py        # BR-06, BR-09 (Chargebacks, Representments & Dynamic Risk)
│       ├── reserve_engine.py           # BR-07 (Rolling Reserves & Holiday Rollover)
│       ├── payout_calculator.py        # BR-08 (Daily Settlement Waterfall)
│       ├── invoice_generator.py        # BR-10 (Monthly Invoices & ITC Rules)
│       └── stretch_goals.py            # Marketplace Split Settlement & Instant Payouts
├── tests/
│   ├── conftest.py                     # Fixtures (Merchants, Calendars, Transactions)
│   ├── test_all_explicit_edge_cases.py # All 8 mandatory edge cases
│   ├── test_br01_br02_mdr_slabs.py
│   ├── test_br03_br11_lifecycle_expiry.py
│   ├── test_br04_settlement_cutoff.py
│   ├── test_br05_refund_netting.py
│   ├── test_br06_br09_chargeback_risk.py
│   ├── test_br07_rolling_reserve.py
│   ├── test_br08_negative_balance_min_payout.py
│   ├── test_br10_monthly_invoice.py
│   ├── test_stretch_goals.py
│   └── test_end_to_end_simulation.py  # 45-day engine simulation
├── data/
│   ├── merchants.csv                   # 8 realistic merchants
│   ├── holidays.csv                    # Declared bank holidays
│   └── events.csv                      # 1,131 lifecycle events across 45 days
└── docs/
    ├── DESIGN_DOCUMENT.md              # Technical design, Mermaid FSM, math proofs
    ├── DECISION_LOG.md                 # Architecture Decision Records (ADR-001 to ADR-007)
    └── VIVA_PREPARATION.md             # In-depth viva Q&A & live modification guide
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Setup
Ensure Python 3.10+ is installed:
```bash
python --version
pip install -r requirements.txt
```

### 2. Run the Settlement Engine Simulation
Execute the master runner to simulate 45 days of settlement cycles:
```bash
python run.py
```
Outputs will be written to `outputs/`:
- `outputs/payouts/payout_YYYY-MM-DD.csv`: Per-merchant daily settlement files.
- `outputs/invoices/`: Formatted tax invoice files for each merchant.
- `outputs/mdr_transactions.csv`: Per-transaction fee & tax audit log.
- `outputs/rejected_events.csv`: Audit log of rejected illegal lifecycle events.

### 3. Run Automated Tests
Execute the full test suite (42 unit and integration tests):
```bash
python -m pytest -v
```

Execute only the 8 mandatory edge cases:
```bash
python -m pytest -v tests/test_all_explicit_edge_cases.py
```

---

## 🎯 Verification of All 8 Explicit Edge Cases

| Edge Case | Description | Test Name | Status |
|---|---|---|---|
| **1** | UPI capture of ₹2,000.00 vs ₹2,000.01 | `test_edge_case_1_upi_slabs` | ✅ Passed |
| **2** | Capture at 23:00:00 exactly vs 23:00:01 | `test_edge_case_2_cutoff_boundary` | ✅ Passed |
| **3** | Refund on Day 180 vs Day 181 | `test_edge_case_3_refund_180_vs_181` | ✅ Passed |
| **4** | Capture on Day 7 after AUTH vs Day 7 + 1s | `test_edge_case_4_capture_day_7_expiry` | ✅ Passed |
| **5** | Chargeback producing negative balance | `test_edge_case_5_negative_balance_carry_forward` | ✅ Passed |
| **6** | Reserve release date falling on a holiday | `test_edge_case_6_reserve_release_on_holiday` | ✅ Passed |
| **7** | Chargeback ratio exactly 1.00% vs > 1.00% | `test_edge_case_7_chargeback_ratio_exactly_1_percent` | ✅ Passed |
| **8** | Payout of ₹99.99 pending for 30 days | `test_edge_case_8_payout_99_99_aging_30_days` | ✅ Passed |

---

## 💡 Viva & Placement Evaluation Prep

Refer to [`docs/VIVA_PREPARATION.md`](docs/VIVA_PREPARATION.md) for in-depth answers to:
- Why MDR is not refunded on customer refunds (Interchange & scheme fee mechanics).
- Rolling reserve release timing & holiday rollovers.
- Negative balance credit protection & frozen reserve releases.
- Live code modification cheatsheet for live viva challenges.

---

## 📄 Submission Checklist

- [x] Repository named **T124-PS-015**
- [x] Command-file driven execution (no UI)
- [x] BR-01 to BR-11 registered and fully implemented
- [x] All 8 explicit edge cases tested and passing
- [x] Comprehensive test suite (42 tests, 100% pass rate)
- [x] Production design document (`docs/DESIGN_DOCUMENT.md`)
- [x] Architecture Decision Records (`docs/DECISION_LOG.md`)
- [x] Placement Viva preparation cheatsheet (`docs/VIVA_PREPARATION.md`)
- [x] Stretch goals implemented (Marketplace splits & Instant settlements)
