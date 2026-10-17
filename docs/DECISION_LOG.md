# Architecture Decision Records (ADR)
## Project: T124-PS-015 · Payment Aggregator Merchant Settlement Engine

This decision log documents key architectural, domain, and data-modelling choices made during the engineering of the settlement engine.

---

### ADR-001: Adoption of Arbitrary-Precision Decimal for All Monetary Operations
- **Status**: Accepted
- **Context**: IEEE 754 floating-point arithmetic introduces non-deterministic binary approximations (e.g., `0.1 + 0.2 = 0.30000000000000004`). In BFSI settlement engines, rounding discrepancies cause cumulative ledger imbalance, auditor non-compliance, and statutory reconciliation failures.
- **Decision**: All financial figures (`amounts`, `mdr`, `gst`, `reserves`, `balances`, `ratios`) are strictly modelled as `decimal.Decimal` with explicit quantization using `ROUND_HALF_UP` to two decimal places (`Decimal("0.01")`).
- **Consequences**: Exact paise precision guaranteed across all test suites, elimination of float casting errors.

---

### ADR-002: Command-Driven Architecture Without Direct UI Coupling
- **Status**: Accepted
- **Context**: The problem statement explicitly specifies a command-file driven engine (`no UI`). Settlement engines in enterprise payment aggregators run as batch worker processes or headless cron jobs triggered by file transfers (SFTP/batch queues).
- **Decision**: Implemented a decoupled command-line interface (`run.py` & `SettlementCLI`) that reads CSV command files, processes chronological lifecycle streams, and generates daily payout CSVs and monthly invoice files.
- **Consequences**: Easy automation, integration testing via CI/CD, and zero overhead from web dependencies.

---

### ADR-003: MDR Retention Policy on Refunds
- **Status**: Accepted
- **Context**: When a merchant refunds a customer, card networks (Visa/Mastercard/RuPay) do not refund interchange and assessment fees. The aggregator also incurs operational costs to process the reversal.
- **Decision**: As codified in **BR-05**, the engine nets the gross refunded principal from the merchant's settlement batch, but keeps the original `mdr_amount` and `gst_amount` intact in aggregator revenues.
- **Consequences**: Matches BFSI standard practices; protected against aggregator margin loss on high-refund merchants.

---

### ADR-004: Strict Waterfall Pipeline Execution Ordering
- **Status**: Accepted
- **Context**: In what sequence should captures, refunds, chargebacks, reserves, and minimum payout checks be processed to avoid circular dependencies and liquidity leakage?
- **Decision**: Codified the invariant sequence under **BR-10**:
  `1. Eligible Captures -> 2. Refund Deductions -> 3. Chargeback Debits -> 4. Representment Credits -> 5. Reserve Withholding -> 6. Negative Balance Freeze Check -> 7. Reserve Release -> 8. Minimum Payout / Aging Evaluation`.
- **Consequences**: Guarantees deterministic ledger outputs; prevents releasing reserves when the merchant is in negative equity.

---

### ADR-005: Dual-Track Ledger for Unsettled Balances & Rolling Reserves Escrow
- **Status**: Accepted
- **Context**: Merchants can have negative balances due to sudden chargebacks. If a rolling reserve matures while the merchant is in deficit, disbursing the reserve creates credit risk.
- **Decision**: Separated `carried_balance` (operating ledger) from `active_reserves` (escrow ledger). Under **BR-08**, if `pre_release_balance < 0`, matured reserve release is blocked until the merchant deposits funds or offsets the deficit through subsequent captures.
- **Consequences**: Absolute protection against aggregator bad debts.

---

### ADR-006: 30-Day Aging Override for Dormant Micro-Balances
- **Status**: Accepted
- **Context**: Small merchants may have balances below ₹100 for extended periods. If unprocessed indefinitely, aggregators accumulate dormant liabilities.
- **Decision**: Track `pending_since_date`. If $D - \text{pending\_since} \ge 30\text{ days}$, release the exact pending amount (e.g. ₹99.99) and reset the timer.
- **Consequences**: Meets statutory unclaimed property guidelines while enforcing the ₹100 floor during normal operations.

---

### ADR-007: Dynamic Risk Rehabilitation via 60-Day Clean Window
- **Status**: Accepted
- **Context**: Merchants downgraded due to chargeback spikes (> 1.00% in trailing 30 days) must have a deterministic path to recover their risk grade.
- **Decision**: Implemented a 60-consecutive-clean-day tracking mechanism (**BR-09**). Every day without chargebacks increments the counter; reaching 60 improves the risk tier by one level.
- **Consequences**: Fair merchant lifecycle management adhering to card brand monitoring program rules.
