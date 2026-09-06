"""Run every connector, then generic change detection. `python -m qr_research.run [source ...]`"""
import sys
from qr_research.connectors.fdic import FDICConnector
from qr_research.connectors.census import CensusConnector
from qr_research.connectors.gateway import GatewayConnector
from qr_research.connectors.gateway_finance import GatewayFinanceConnector
from qr_research.connectors.sec_form_d import SECFormDConnector
from qr_research.connectors.bankruptcy import BankruptcyConnector
from qr_research.connectors.usaspending import USASpendingConnector
from qr_research.connectors.irs_990 import IRS990Connector
from qr_research.scanner.diff import detect_changes

CONNECTORS = {c.source_id: c for c in (FDICConnector(), CensusConnector(), GatewayConnector(), GatewayFinanceConnector(), SECFormDConnector(), BankruptcyConnector(), USASpendingConnector(), IRS990Connector())}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(CONNECTORS)
    for sid in wanted:
        print(CONNECTORS[sid].run())
        print(f"  changes: {detect_changes(sid)}")
