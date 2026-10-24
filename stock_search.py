"""
株式コード・企業名 検索および解決モジュール
- 証券コード（例: 8058, 7203, AAPL）の正規化
- 企業名（日本語/英語 例: トヨタ, 三菱商事, Apple）からの銘柄検索
"""

import re
import urllib.parse
import unicodedata
import requests
from bs4 import BeautifulSoup
import yfinance as yf

def normalize_input(query: str) -> str:
    """入力文字列の全角半角正規化・空白除去"""
    if not query:
        return ""
    # 全角英数字を半角に変換
    normalized = unicodedata.normalize("NFKC", str(query)).strip()
    return normalized

def is_japan_stock_code(query: str) -> bool:
    """4桁数字（または英字混じり新コード）の日本株コードか判定"""
    # 伝統的な4桁数字、または新設の英数字4桁コード（例: 130Aなど）
    return bool(re.match(r"^\d{4}$", query) or re.match(r"^\d{3}[A-Z]$", query, re.I))

def search_stocks(query: str, max_results: int = 10) -> list[dict]:
    """
    入力されたキーワード（コードまたは会社名）から候補となる銘柄一覧を検索する
    戻り値: [{'symbol': '8058.T', 'name': '三菱商事', 'market': '東証PRM', 'currency': 'JPY'}, ...]
    """
    q = normalize_input(query)
    if not q:
        return []

    results = []
    seen_symbols = set()

    # 1. 4桁証券コード（日本株）の場合
    if is_japan_stock_code(q):
        symbol = f"{q.upper()}.T"
        # 簡易確認
        try:
            t = yf.Ticker(symbol)
            info = t.info
            name = info.get("longName") or info.get("shortName") or f"銘柄コード {q}"
            return [{
                "symbol": symbol,
                "code": q.upper(),
                "name": name,
                "market": "東証 (東京証券取引所)",
                "currency": info.get("currency", "JPY")
            }]
        except Exception:
            return [{
                "symbol": symbol,
                "code": q.upper(),
                "name": f"日本株 ({q})",
                "market": "東証",
                "currency": "JPY"
            }]

    # 2. すでにサフィックス付きシンボルの場合（例: 8058.T, AAPL）
    if re.match(r"^[A-Za-z0-9\.\=\-]+$", q):
        clean_q = q.upper()
        # 日本株で.Tをつけていない数字コードの場合
        if clean_q.isdigit() and len(clean_q) == 4:
            clean_q = f"{clean_q}.T"
            
        try:
            t = yf.Ticker(clean_q)
            info = t.info
            if info and (info.get("regularMarketPrice") or info.get("currentPrice") or info.get("shortName")):
                name = info.get("longName") or info.get("shortName") or clean_q
                results.append({
                    "symbol": clean_q,
                    "code": clean_q.replace(".T", ""),
                    "name": name,
                    "market": info.get("exchange", "米国/主要市場"),
                    "currency": info.get("currency", "USD")
                })
                seen_symbols.add(clean_q)
        except Exception:
            pass

    # 3. 日本語会社名によるYahoo Finance Japan検索
    yj_results = _search_yahoo_japan(q)
    for item in yj_results:
        sym = item["symbol"]
        if sym not in seen_symbols:
            results.append(item)
            seen_symbols.add(sym)
            if len(results) >= max_results:
                return results

    # 4. yfinance Search (英語社名やティッカー検索用)
    try:
        yf_search = yf.Search(q, max_results=max_results)
        for quote in getattr(yf_search, "quotes", []):
            sym = quote.get("symbol")
            if not sym or sym in seen_symbols:
                continue
            name = quote.get("longname") or quote.get("shortname") or sym
            market = quote.get("exchange") or quote.get("quoteType", "")
            results.append({
                "symbol": sym,
                "code": sym.replace(".T", ""),
                "name": name,
                "market": market,
                "currency": "JPY" if sym.endswith(".T") else "USD"
            })
            seen_symbols.add(sym)
            if len(results) >= max_results:
                break
    except Exception:
        pass

    return results

def _search_yahoo_japan(query: str) -> list[dict]:
    """Yahoo Finance Japanの検索結果ページから日本株候補を取得"""
    candidates = []
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://finance.yahoo.co.jp/search/?query={encoded}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        seen_codes = set()

        # 検索結果の各リンクを走査
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            # /quote/XXXX.T または /quote/XXXX のパターン
            m = re.search(r"/quote/([0-9]{4}[A-Za-z]?|[A-Za-z0-9]+)(\.T)?$", href)
            if not m:
                continue

            raw_code = m.group(1)
            # 日本株の4桁コードを優先
            if len(raw_code) == 4 and raw_code.isdigit():
                symbol = f"{raw_code}.T"
            else:
                symbol = raw_code

            if symbol in seen_codes:
                continue

            text = a.get_text(separator=" ", strip=True)
            if not text:
                continue

            # テキストから企業名を抽出（例: "7203 PRM トヨタ自動車(株) 3,105..."）
            # 不要な株価情報や市場名を整形
            name = _extract_clean_name(text, raw_code)

            # 市場判定
            market = "東証"
            if "PRM" in text or "プライム" in text:
                market = "東証プライム"
            elif "STD" in text or "スタンダード" in text:
                market = "東証スタンダード"
            elif "GRT" in text or "グロース" in text:
                market = "東証グロース"

            candidates.append({
                "symbol": symbol,
                "code": raw_code,
                "name": name,
                "market": market,
                "currency": "JPY" if symbol.endswith(".T") else "USD"
            })
            seen_codes.add(symbol)
            if len(candidates) >= 8:
                break

    except Exception:
        pass

    return candidates

def _extract_clean_name(raw_text: str, code: str) -> str:
    """Yahoo Financeの検索テキストから銘柄名を綺麗に抽出"""
    # 例: "7203 PRM トヨタ自動車(株) 3,105 +21(+0.68%) 10/23"
    t = raw_text.replace(code, "").strip()
    for m in ["PRM", "STD", "GRT", "名証", "福証", "札証", "東証"]:
        t = t.replace(m, "").strip()
    
    # 株価（数字とカンマ、+/-、%）が続く直前でカット
    m_price = re.search(r"[\d,]+(\.\d+)?\s*[\+\-]", t)
    if m_price:
        t = t[:m_price.start()].strip()
    
    # 括弧や記号を整える
    t = re.sub(r"\s+", " ", t).strip()
    return t if t else f"コード {code}"
