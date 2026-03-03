from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class AssetType(str, Enum):
    STOCK       = "stock"
    ETF         = "etf"
    MUTUAL_FUND = "mutual_fund"
    CRYPTO      = "crypto"
    BOND        = "bond"
    OPTION      = "option"
    OTHER       = "other"

class BrokerName(str, Enum):
    ZERODHA             = "Zerodha"
    INTERACTIVE_BROKERS = "Interactive Brokers"
    SHAREKHAN           = "Sharekhan"
    ETORO               = "eToro"
    AIONION             = "Aionion Capital"

class Holding(BaseModel):
    broker:            BrokerName
    symbol:            str
    name:              str
    asset_type:        AssetType
    quantity:          float
    average_price:     float
    current_price:     float
    current_value:     float
    invested_value:    float
    pnl:               float
    pnl_percent:       float
    currency:          str           = "INR"
    exchange:          Optional[str] = None
    sector:            Optional[str] = None
    owner:             Optional[str] = "selvam"    # selvam | radhika
    sub_account:       Optional[str] = None        # copy trader username
    day_change:        Optional[float] = None
    day_change_percent: Optional[float] = None

class Bond(BaseModel):
    broker:           BrokerName
    isin:             str
    name:             str
    symbol:           str
    quantity:         float
    principal_amount: float
    coupon_rate:      float
    maturity_date:    Optional[str]  = None
    call_date:        Optional[str]  = None
    ytm:              Optional[float] = None
    ytc:              Optional[float] = None
    trade_date:       Optional[str]  = None
    currency:         str            = "INR"
    exchange:         str            = "NSE"
    owner:            Optional[str]  = "radhika"

class BrokerSummary(BaseModel):
    broker:            BrokerName
    connected:         bool
    total_value:       float
    total_invested:    float
    total_pnl:         float
    total_pnl_percent: float
    cash_balance:      float
    holdings_count:    int
    currency:          str           = "INR"
    last_updated:      Optional[str] = None
    owner:             Optional[str] = "selvam"

class PortfolioSummary(BaseModel):
    total_value:       float
    total_invested:    float
    total_pnl:         float
    total_pnl_percent: float
    day_pnl:           float
    day_pnl_percent:   float
    brokers:           List[BrokerSummary]
    total_holdings:    int
    selvam_value:      Optional[float] = 0
    radhika_value:     Optional[float] = 0

class PerformancePoint(BaseModel):
    date:   str
    value:  float
    broker: Optional[str] = None
