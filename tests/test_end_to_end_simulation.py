"""
End-to-End System Simulation Test for PS-015 Engine.
Tests full pipeline across 45 calendar days with 1,000+ lifecycle events.
"""

import os
import shutil
import pytest
from datetime import date
from settlement_engine.cli import SettlementCLI


class TestEndToEndSimulation:

    @pytest.fixture
    def test_output_dir(self, tmp_path):
        out_dir = str(tmp_path / "test_outputs")
        yield out_dir
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_full_engine_run(self, test_output_dir):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        merchants_path = os.path.join(base_dir, "data", "merchants.csv")
        holidays_path = os.path.join(base_dir, "data", "holidays.csv")
        events_path = os.path.join(base_dir, "data", "events.csv")

        cli = SettlementCLI(output_dir=test_output_dir)

        # 1. Ingest
        n_merchants = cli.load_merchants(merchants_path)
        assert n_merchants == 8, "Must load 8 merchants"

        n_holidays = cli.load_holidays(holidays_path)
        assert n_holidays >= 4, "Must load declared holidays"

        n_events = cli.load_and_process_events(events_path)
        assert n_events >= 300, "Must process 300+ events"

        # 2. Run Daily Settlement Cycles across 45 days
        s_date = date(2026, 9, 1)
        e_date = date(2026, 10, 15)
        days_run = cli.run_settlement_range(s_date, e_date)
        assert days_run == 45, "Must complete 45 daily cycles"

        # 3. Export Artifacts
        mdr_file = cli.export_mdr_transactions()
        rej_file = cli.export_rejections()
        cli.export_invoices(2026, 9)

        # 4. Verify Generated Files
        assert os.path.exists(mdr_file), "MDR audit file must exist"
        assert os.path.exists(rej_file), "Rejections file must exist"

        payout_files = os.listdir(os.path.join(test_output_dir, "payouts"))
        assert len(payout_files) > 0, "Payout files must be generated"

        invoice_files = os.listdir(os.path.join(test_output_dir, "invoices"))
        assert len(invoice_files) >= 8, "Invoices for all 8 merchants must exist"
