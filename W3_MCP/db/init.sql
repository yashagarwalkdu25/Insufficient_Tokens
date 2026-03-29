-- Indian Financial Intelligence MCP Server - Database Initialization
-- PostgreSQL 16 schema for finint database

BEGIN;

-- ============================================================
-- TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    keycloak_id   VARCHAR(255) UNIQUE NOT NULL,
    username      VARCHAR(255) NOT NULL,
    email         VARCHAR(255),
    tier          VARCHAR(50) NOT NULL DEFAULT 'free',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portfolios (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    symbol     VARCHAR(50) NOT NULL,
    isin       VARCHAR(12),
    quantity   INTEGER NOT NULL,
    avg_price  NUMERIC(12,2) NOT NULL,
    added_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);

CREATE TABLE IF NOT EXISTS watchlists (
    id       SERIAL PRIMARY KEY,
    user_id  INTEGER REFERENCES users(id) ON DELETE CASCADE,
    symbol   VARCHAR(50) NOT NULL,
    isin     VARCHAR(12),
    added_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id               BIGSERIAL PRIMARY KEY,
    user_id          VARCHAR(255) NOT NULL,
    tier             VARCHAR(50) NOT NULL,
    tool_name        VARCHAR(255) NOT NULL,
    timestamp        TIMESTAMPTZ DEFAULT NOW(),
    latency_ms       INTEGER,
    cache_hit        BOOLEAN DEFAULT FALSE,
    source_used      VARCHAR(255),
    request_metadata JSONB
);

CREATE TABLE IF NOT EXISTS isin_mapping (
    isin                 VARCHAR(12) PRIMARY KEY,
    nse_symbol           VARCHAR(50) UNIQUE,
    bse_scrip_code       VARCHAR(20),
    yfinance_ticker      VARCHAR(50),
    alpha_vantage_ticker VARCHAR(50),
    company_name         VARCHAR(255) NOT NULL,
    sector               VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS macro_data (
    id         SERIAL PRIMARY KEY,
    indicator  VARCHAR(100) NOT NULL,
    value      NUMERIC(15,4),
    unit       VARCHAR(50),
    source     VARCHAR(100) DEFAULT 'RBI DBIE',
    date       DATE NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(indicator, date)
);

CREATE TABLE IF NOT EXISTS cached_research (
    id            SERIAL PRIMARY KEY,
    symbol        VARCHAR(50) NOT NULL,
    analysis_json JSONB NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    expires_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tier_upgrade_requests (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER REFERENCES users(id) ON DELETE CASCADE,
    requested_tier VARCHAR(50) NOT NULL,
    status         VARCHAR(50) DEFAULT 'pending',
    requested_at   TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at    TIMESTAMPTZ,
    reviewed_by    INTEGER REFERENCES users(id),
    notes          TEXT
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_audit_log_user_timestamp ON audit_log(user_id, timestamp);
CREATE INDEX idx_audit_log_tool_name      ON audit_log(tool_name);
CREATE INDEX idx_isin_mapping_nse_symbol  ON isin_mapping(nse_symbol);
CREATE INDEX idx_portfolios_user_id       ON portfolios(user_id);
CREATE INDEX idx_watchlists_user_id       ON watchlists(user_id);
CREATE INDEX idx_tier_upgrade_user_status ON tier_upgrade_requests(user_id, status);

-- ============================================================
-- SEED DATA: Nifty 50 ISIN Mappings (25 major stocks)
-- ============================================================

INSERT INTO isin_mapping (isin, nse_symbol, bse_scrip_code, yfinance_ticker, alpha_vantage_ticker, company_name, sector) VALUES
('INE002A01018', 'RELIANCE',   '500325', 'RELIANCE.NS',   'RELIANCE.BSE',   'Reliance Industries Limited',          'Oil & Gas / Conglomerate'),
('INE467B01029', 'TCS',        '532540', 'TCS.NS',        'TCS.BSE',        'Tata Consultancy Services Limited',    'Information Technology'),
('INE040A01034', 'HDFCBANK',   '500180', 'HDFCBANK.NS',   'HDFCBANK.BSE',   'HDFC Bank Limited',                    'Banking'),
('INE009A01021', 'INFY',       '500209', 'INFY.NS',       'INFY.BSE',       'Infosys Limited',                      'Information Technology'),
('INE090A01021', 'ICICIBANK',  '532174', 'ICICIBANK.NS',  'ICICIBANK.BSE',  'ICICI Bank Limited',                   'Banking'),
('INE030A01027', 'HINDUNILVR', '500696', 'HINDUNILVR.NS', 'HINDUNILVR.BSE', 'Hindustan Unilever Limited',           'FMCG'),
('INE154A01025', 'ITC',        '500875', 'ITC.NS',        'ITC.BSE',        'ITC Limited',                          'FMCG / Conglomerate'),
('INE062A01020', 'SBIN',       '500112', 'SBIN.NS',       'SBIN.BSE',       'State Bank of India',                  'Banking'),
('INE397D01024', 'BHARTIARTL', '532454', 'BHARTIARTL.NS', 'BHARTIARTL.BSE', 'Bharti Airtel Limited',                'Telecommunications'),
('INE237A01028', 'KOTAKBANK',  '500247', 'KOTAKBANK.NS',  'KOTAKBANK.BSE',  'Kotak Mahindra Bank Limited',          'Banking'),
('INE018A01030', 'LT',         '500510', 'LT.NS',         'LT.BSE',         'Larsen & Toubro Limited',              'Infrastructure / Engineering'),
('INE238A01034', 'AXISBANK',   '532215', 'AXISBANK.NS',   'AXISBANK.BSE',   'Axis Bank Limited',                    'Banking'),
('INE296A01024', 'BAJFINANCE', '500034', 'BAJFINANCE.NS', 'BAJFINANCE.BSE', 'Bajaj Finance Limited',                'Financial Services'),
('INE585B01010', 'MARUTI',     '532500', 'MARUTI.NS',     'MARUTI.BSE',     'Maruti Suzuki India Limited',          'Automobile'),
('INE860A01027', 'HCLTECH',    '532281', 'HCLTECH.NS',    'HCLTECH.BSE',    'HCL Technologies Limited',             'Information Technology'),
('INE280A01028', 'TITAN',      '500114', 'TITAN.NS',      'TITAN.BSE',      'Titan Company Limited',                'Consumer Goods'),
('INE044A01036', 'SUNPHARMA',  '524715', 'SUNPHARMA.NS',  'SUNPHARMA.BSE',  'Sun Pharmaceutical Industries Limited', 'Pharmaceuticals'),
('INE155A01022', 'TATAMOTORS', '500570', 'TATAMOTORS.NS', 'TATAMOTORS.BSE', 'Tata Motors Limited',                  'Automobile'),
('INE075A01022', 'WIPRO',      '507685', 'WIPRO.NS',      'WIPRO.BSE',      'Wipro Limited',                        'Information Technology'),
('INE239A01016', 'NESTLEIND',  '500790', 'NESTLEIND.NS',  'NESTLEIND.BSE',  'Nestle India Limited',                 'FMCG'),
('INE271C01023', 'DLF',        '532868', 'DLF.NS',        'DLF.BSE',        'DLF Limited',                          'Real Estate'),
('INE423A01024', 'ADANIENT',   '512599', 'ADANIENT.NS',   'ADANIENT.BSE',   'Adani Enterprises Limited',            'Conglomerate'),
('INE918I01026', 'BAJAJFINSV', '532978', 'BAJAJFINSV.NS', 'BAJAJFINSV.BSE', 'Bajaj Finserv Limited',                'Financial Services'),
('INE669C01036', 'TECHM',      '532755', 'TECHM.NS',      'TECHM.BSE',      'Tech Mahindra Limited',                'Information Technology'),
('INE733E01010', 'NTPC',       '532555', 'NTPC.NS',       'NTPC.BSE',       'NTPC Limited',                         'Power / Energy')
ON CONFLICT (isin) DO NOTHING;

-- ============================================================
-- SEED DATA: Current Macro Indicators
-- ============================================================

INSERT INTO macro_data (indicator, value, unit, source, date) VALUES
('repo_rate',            6.5000, 'percent', 'RBI',      CURRENT_DATE),
('reverse_repo_rate',    3.3500, 'percent', 'RBI',      CURRENT_DATE),
('crr',                  4.5000, 'percent', 'RBI',      CURRENT_DATE),
('slr',                 18.0000, 'percent', 'RBI',      CURRENT_DATE),
('cpi_inflation',        4.2000, 'percent', 'MOSPI',    CURRENT_DATE),
('wpi_inflation',        1.3000, 'percent', 'MOSPI',    CURRENT_DATE),
('gdp_growth',           6.5000, 'percent', 'RBI DBIE', CURRENT_DATE),
('forex_reserves',     650.0000, 'bn_usd',  'RBI',      CURRENT_DATE),
('usd_inr',            83.4000, 'INR/USD',  'RBI',      CURRENT_DATE)
ON CONFLICT (indicator, date) DO NOTHING;

-- ============================================================
-- SEED DATA: Initial Admin User
-- ============================================================

INSERT INTO users (keycloak_id, username, email, tier) VALUES
('00000000-0000-0000-0000-000000000001', 'admin', 'admin@finint.local', 'admin')
ON CONFLICT (keycloak_id) DO NOTHING;

COMMIT;
