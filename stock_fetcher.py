"""
株式データ取得モジュール (yfinance)
- 企業の基本指標（株価、利回り、PER、PBR、配当性向など）
- 過去の配当金履歴（年間合計、増配/減配判定）
- 過去数年分の決算・財務諸表（損益、貸借対照表、キャッシュフロー）
"""

import datetime
import pandas as pd
import numpy as np
import yfinance as yf

def fetch_stock_data(symbol: str) -> dict:
    """
    指定されたシンボル（例: 8058.T, AAPL）の財務・配当・株価データをまとめて取得する
    """
    ticker = yf.Ticker(symbol)
    
    # 1. 基本情報の取得
    try:
        info = ticker.info or {}
    except Exception:
        info = {}

    # 株価情報
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 0.0
    previous_close = info.get("previousClose") or current_price
    price_change = current_price - previous_close if previous_close else 0.0
    price_change_pct = (price_change / previous_close * 100) if previous_close else 0.0

    # 配当利回り（yfinanceの仕様差分を正規化: 0.035 なら 3.5%に変換）
    raw_yield = info.get("dividendYield") or info.get("trailingAnnualDividendYield") or 0.0
    if 0 < raw_yield < 0.2:  # 小数点表記の場合
        dividend_yield = raw_yield * 100.0
    elif raw_yield >= 0.2:
        dividend_yield = raw_yield
    else:
        dividend_yield = 0.0

    # 配当性向（payoutRatio: 0.45 なら 45%）
    raw_payout = info.get("payoutRatio")
    if raw_payout is not None and not np.isnan(raw_payout):
        if 0 < raw_payout <= 2.0:
            payout_ratio = raw_payout * 100.0
        else:
            payout_ratio = float(raw_payout)
    else:
        payout_ratio = None

    # 基本情報の整理
    basic_info = {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName") or symbol,
        "currency": info.get("currency", "JPY" if symbol.endswith(".T") else "USD"),
        "current_price": float(current_price),
        "previous_close": float(previous_close),
        "price_change": float(price_change),
        "price_change_pct": float(price_change_pct),
        "dividend_yield": round(float(dividend_yield), 2),
        "dividend_rate": info.get("dividendRate") or info.get("trailingAnnualDividendRate") or 0.0,
        "payout_ratio": round(float(payout_ratio), 1) if payout_ratio is not None else None,
        "per": round(float(info.get("trailingPE")), 2) if info.get("trailingPE") else None,
        "forward_pe": round(float(info.get("forwardPE")), 2) if info.get("forwardPE") else None,
        "pbr": round(float(info.get("priceToBook")), 2) if info.get("priceToBook") else None,
        "roe": round(float(info.get("returnOnEquity") * 100), 2) if info.get("returnOnEquity") else None,
        "market_cap": info.get("marketCap"),
        "sector": info.get("sector", "その他"),
        "industry": info.get("industry", "その他"),
        "country": info.get("country", "Japan" if symbol.endswith(".T") else "US"),
        "summary": info.get("longBusinessSummary", "企業概要データはありません。"),
    }

    # 2. 過去の配当履歴の整理
    dividend_df = _process_dividends(ticker)

    # 3. 過去数年分の財務データの整理（損益・貸借・CF）
    financials_data = _process_financials(ticker)

    # 配当性向がinfoで取れなかった場合、直近の純利益と配当総額から再計算
    if basic_info["payout_ratio"] is None and len(dividend_df) > 0 and len(financials_data["history"]) > 0:
        latest_div = dividend_df["dividend"].iloc[-1]
        latest_eps = financials_data["history"][-1].get("eps")
        if latest_div and latest_eps and latest_eps > 0:
            calc_payout = (latest_div / latest_eps) * 100.0
            basic_info["payout_ratio"] = round(float(calc_payout), 1)

    return {
        "basic_info": basic_info,
        "dividend_df": dividend_df,
        "financials": financials_data
    }

def _process_dividends(ticker: yf.Ticker) -> pd.DataFrame:
    """配当履歴を取得し、年間配当金および前年比増減をまとめる"""
    try:
        divs = ticker.dividends
        if divs is None or len(divs) == 0:
            return pd.DataFrame(columns=["year", "dividend", "change_pct", "status"])
        
        # Series to DataFrame
        df = divs.reset_index()
        # 日付カラムの名前を正規化
        date_col = df.columns[0]
        df["year"] = pd.to_datetime(df[date_col]).dt.year

        # 年ごとに集計
        annual = df.groupby("year")["Dividends"].sum().reset_index()
        annual.columns = ["year", "dividend"]

        # 今年（進行年度）の配当が中間配当だけで低く見えることがあるため、
        # 直近10年間を対象にする
        current_year = datetime.datetime.now().year
        annual = annual[annual["year"] >= (current_year - 10)].copy()

        # 前年比の計算
        annual["prev_dividend"] = annual["dividend"].shift(1)
        annual["change_pct"] = ((annual["dividend"] - annual["prev_dividend"]) / annual["prev_dividend"] * 100).round(1)

        def determine_status(row):
            if pd.isna(row["prev_dividend"]):
                return "初回/基準"
            diff = row["dividend"] - row["prev_dividend"]
            if diff > 0.01:
                return "増配"
            elif diff < -0.01:
                return "減配"
            else:
                return "維持"

        annual["status"] = annual.apply(determine_status, axis=1)
        annual["dividend"] = annual["dividend"].round(2)
        return annual[["year", "dividend", "change_pct", "status"]]

    except Exception:
        return pd.DataFrame(columns=["year", "dividend", "change_pct", "status"])

def _process_financials(ticker: yf.Ticker) -> dict:
    """損益計算書・貸借対照表・キャッシュフロー計算書から推移データを整理"""
    result = {
        "history": [],
        "latest_equity_ratio": None,
        "latest_fcf": None,
        "avg_revenue_growth": None,
        "avg_operating_profit_growth": None,
    }

    try:
        inc = ticker.financials
        bs = ticker.balance_sheet
        cf = ticker.cashflow

        if inc is None or inc.empty:
            inc = ticker.income_stmt

        if inc is None or inc.empty:
            return result

        # 年月（列名）を古い順にソート
        dates = sorted(list(inc.columns))
        history_list = []

        for d in dates:
            year_str = pd.to_datetime(d).strftime("%Y/%m")
            
            # 売上高
            rev = _get_row_value(inc, d, ["Total Revenue", "Operating Revenue"])
            # 営業利益
            op_inc = _get_row_value(inc, d, ["Operating Income", "Operating Profit", "Total Operating Income"])
            # 純利益
            net_inc = _get_row_value(inc, d, ["Net Income", "Net Income Common Stockholders"])
            # EPS
            eps = _get_row_value(inc, d, ["Diluted EPS", "Basic EPS"])

            # 貸借対照表（自己資本比率）
            tot_assets = _get_row_value(bs, d, ["Total Assets"]) if bs is not None and d in bs.columns else None
            tot_equity = _get_row_value(bs, d, ["Stockholders Equity", "Total Equity Gross Minority Interest", "Common Stock Equity"]) if bs is not None and d in bs.columns else None
            equity_ratio = (tot_equity / tot_assets * 100) if (tot_assets and tot_equity and tot_assets > 0) else None

            # キャッシュフロー
            op_cf = _get_row_value(cf, d, ["Operating Cash Flow", "Cash Flowsfromusedin Operating Activities"]) if cf is not None and d in cf.columns else None
            inv_cf = _get_row_value(cf, d, ["Investing Cash Flow", "Cash Flowsfromusedin Investing Activities"]) if cf is not None and d in cf.columns else None
            fcf = _get_row_value(cf, d, ["Free Cash Flow"]) if cf is not None and d in cf.columns else None
            if fcf is None and op_cf is not None and inv_cf is not None:
                fcf = op_cf + inv_cf

            history_list.append({
                "date": year_str,
                "revenue": rev,
                "operating_income": op_inc,
                "net_income": net_inc,
                "eps": round(float(eps), 2) if eps else None,
                "equity_ratio": round(float(equity_ratio), 1) if equity_ratio else None,
                "operating_cf": op_cf,
                "free_cf": fcf,
            })

        result["history"] = history_list

        # 直近値の抽出
        if history_list:
            last = history_list[-1]
            result["latest_equity_ratio"] = last["equity_ratio"]
            result["latest_fcf"] = last["free_cf"]

            # 売上成長率の平均
            revs = [h["revenue"] for h in history_list if h["revenue"] is not None and h["revenue"] > 0]
            if len(revs) >= 2:
                growth = (revs[-1] - revs[0]) / revs[0] * 100 / (len(revs) - 1)
                result["avg_revenue_growth"] = round(float(growth), 1)

            # 営業利益成長率の平均
            ops = [h["operating_income"] for h in history_list if h["operating_income"] is not None]
            if len(ops) >= 2 and ops[0] > 0:
                op_growth = (ops[-1] - ops[0]) / abs(ops[0]) * 100 / (len(ops) - 1)
                result["avg_operating_profit_growth"] = round(float(op_growth), 1)

    except Exception:
        pass

    return result

def _get_row_value(df: pd.DataFrame, col, possible_keys: list[str]):
    """DataFrameの指定列から、複数候補キーのいずれかに一致する値を取得"""
    if df is None or df.empty or col not in df.columns:
        return None
    for k in possible_keys:
        if k in df.index:
            val = df.loc[k, col]
            if pd.notna(val):
                return float(val)
    return None
