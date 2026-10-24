"""
高配当株 魅力度スコアリングおよび総合分析エンジン
- 6大指標（利回り、配当性向、増配力、業績安定性、財務健全性、割安度）のスコアリング
- 100点満点評価およびランク判定 (S/A/B/C)
- 強み、注意すべきリスク要因のアラート生成
"""

from config import (
    RANK_THRESHOLDS,
    MAX_SCORES,
    YIELD_STANDARDS,
    PAYOUT_STANDARDS,
    FINANCIAL_SAFETY,
    VALUATION_STANDARDS,
)

def analyze_stock(data: dict) -> dict:
    """
    取得データをもとに高配当株としての総合魅力度を分析・判定する
    """
    basic = data.get("basic_info", {})
    div_df = data.get("dividend_df")
    financials = data.get("financials", {})

    scores = {}
    details = {}
    strengths = []
    risks = []

    # -------------------------------------------------------------
    # 1. 配当利回りスコア (Max 20点)
    # -------------------------------------------------------------
    y = basic.get("dividend_yield", 0.0)
    max_y = MAX_SCORES["yield_score"]

    if y >= YIELD_STANDARDS["excellent"]:
        s_yield = max_y
        comm_yield = f"利回り {y:.2f}% は極めて魅力的です（4.0%以上の最高水準）。"
        strengths.append(f"高い配当利回り ({y:.2f}%)")
    elif y >= YIELD_STANDARDS["good"]:
        s_yield = int(max_y * 0.85)
        comm_yield = f"利回り {y:.2f}% は良好な高水準です（3.5%以上）。"
        strengths.append(f"良好な配当利回り ({y:.2f}%)")
    elif y >= YIELD_STANDARDS["fair"]:
        s_yield = int(max_y * 0.65)
        comm_yield = f"利回り {y:.2f}% は中水準です。"
    elif y >= YIELD_STANDARDS["low"]:
        s_yield = int(max_y * 0.4)
        comm_yield = f"利回り {y:.2f}% は高配当株としてはやや控えめです。"
        risks.append(f"配当利回りがやや低い ({y:.2f}%)")
    elif y > 0:
        s_yield = int(max_y * 0.15)
        comm_yield = f"利回り {y:.2f}% は低水準です。"
        risks.append(f"低利回り水準 ({y:.2f}%)")
    else:
        s_yield = 0
        comm_yield = "無配当、または配当データがありません。"
        risks.append("現在無配、または配当実績なし")

    scores["yield_score"] = s_yield
    details["yield"] = {
        "score": s_yield,
        "max_score": max_y,
        "value": f"{y:.2f}%",
        "comment": comm_yield
    }

    # -------------------------------------------------------------
    # 2. 配当性向（減配リスク）スコア (Max 20点)
    # -------------------------------------------------------------
    payout = basic.get("payout_ratio")
    max_p = MAX_SCORES["payout_score"]

    if payout is None:
        s_payout = int(max_p * 0.5)
        comm_payout = "配当性向のデータが取得できませんでした（中間値で評価）。"
    elif payout < 0:
        s_payout = 0
        comm_payout = f"純利益が赤字の中で配当を出している状態です（タコ足配当）。"
        risks.append("最終赤字下での配当（タコ足配当の危険あり）")
    elif payout > PAYOUT_STANDARDS["danger_threshold"]:
        s_payout = 2
        comm_payout = f"配当性向 {payout:.1f}% は100%を超えており、利益以上の配当金を出しています。減配リスクが非常に高いです。"
        risks.append(f"配当性向が100%超 ({payout:.1f}%) で減配リスク大")
    elif payout > PAYOUT_STANDARDS["caution_max"]:
        s_payout = int(max_p * 0.4)
        comm_payout = f"配当性向 {payout:.1f}% は高めで、将来の増配余地や減配への抵抗力に注意が必要です。"
        risks.append(f"配当性向が高水準 ({payout:.1f}%)")
    elif payout >= PAYOUT_STANDARDS["ideal_min"] and payout <= PAYOUT_STANDARDS["ideal_max"]:
        s_payout = max_p
        comm_payout = f"配当性向 {payout:.1f}% は理想的なレンジ（30〜60%）で、株主還元と成長投資のバランスが良好です。"
        strengths.append(f"健全な配当性向 ({payout:.1f}%)")
    elif payout < PAYOUT_STANDARDS["ideal_min"]:
        s_payout = int(max_p * 0.75)
        comm_payout = f"配当性向 {payout:.1f}% は低めで減配リスクは極めて低いですが、利益に対する還元余地がまだ残されています。"
        strengths.append(f"配当性向に余裕あり ({payout:.1f}%)")
    else:
        s_payout = int(max_p * 0.7)
        comm_payout = f"配当性向 {payout:.1f}% は許容範囲内です。"

    scores["payout_score"] = s_payout
    details["payout"] = {
        "score": s_payout,
        "max_score": max_p,
        "value": f"{payout:.1f}%" if payout is not None else "N/A",
        "comment": comm_payout
    }

    # -------------------------------------------------------------
    # 3. 配当継続力・増配実績スコア (Max 20点)
    # -------------------------------------------------------------
    max_h = MAX_SCORES["history_score"]
    cut_count = 0
    consecutive_increase = 0
    years_count = len(div_df) if div_df is not None else 0

    if div_df is not None and years_count >= 3:
        statuses = div_df["status"].tolist()
        # 直近数年での減配回数を集計
        cut_count = statuses.count("減配")
        
        # 直近からの連続増配・維持の年数をカウント
        rev_statuses = list(reversed(statuses))
        for st in rev_statuses:
            if st in ["増配", "維持"]:
                consecutive_increase += 1
            else:
                break

        if cut_count == 0 and consecutive_increase >= 5:
            s_history = max_h
            comm_history = f"直近5年以上減配がなく、連続増配・累進配当を維持しています。"
            strengths.append("過去5年以上減配なし（増配・維持継続）")
        elif cut_count == 0:
            s_history = int(max_h * 0.85)
            comm_history = f"確認可能な期間において減配がなく、安定した配当方針です。"
            strengths.append("非減配の実績（安定配当方針）")
        elif cut_count == 1:
            s_history = int(max_h * 0.55)
            comm_history = f"過去に1回減配がありますが、概ね安定しています。"
        else:
            s_history = int(max_h * 0.25)
            comm_history = f"過去5年以内に複数回（{cut_count}回）の減配実績があり、業績連動での減配リスクがあります。"
            risks.append(f"過去に複数回減配あり（計{cut_count}回）")
    elif years_count > 0:
        s_history = int(max_h * 0.5)
        comm_history = "配当履歴の期間が短いため、標準点として評価しています。"
    else:
        s_history = 0
        comm_history = "過去の配当履歴が取得できませんでした。"

    scores["history_score"] = s_history
    details["history"] = {
        "score": s_history,
        "max_score": max_h,
        "value": f"減配{cut_count}回 / 継続{consecutive_increase}年" if years_count >= 3 else "データ少",
        "comment": comm_history
    }

    # -------------------------------------------------------------
    # 4. 業績・収益の安定性スコア (Max 15点)
    # -------------------------------------------------------------
    max_perf = MAX_SCORES["performance_score"]
    history = financials.get("history", [])
    rev_growth = financials.get("avg_revenue_growth")
    op_growth = financials.get("avg_operating_profit_growth")

    s_perf = 0
    all_profitable = False
    if history:
        # 過去の純利益が全てプラスか判定
        net_incomes = [h["net_income"] for h in history if h.get("net_income") is not None]
        if net_incomes and all(n > 0 for n in net_incomes):
            all_profitable = True
            s_perf += 8
            strengths.append("過去数年間継続して黒字を達成")
        elif net_incomes:
            s_perf += 2
            risks.append("過去に最終赤字の期が存在")

        # 売上成長
        if rev_growth is not None and rev_growth > 0:
            s_perf += 4
            strengths.append(f"売上高が成長傾向 (年平均約+{rev_growth:.1f}%)")
        elif rev_growth is not None and rev_growth < -5.0:
            risks.append(f"売上高が減少傾向 (年平均約{rev_growth:.1f}%)")

        # 営業利益成長
        if op_growth is not None and op_growth > 0:
            s_perf += 3
        
        s_perf = min(s_perf, max_perf)
        comm_perf = f"黒字維持力: {'◎ 全期黒字' if all_profitable else '△ 赤字歴あり'}, 売上成長: {f'{rev_growth:+.1f}%' if rev_growth else 'N/A'}"
    else:
        s_perf = int(max_perf * 0.5)
        comm_perf = "詳細な損益計算書の推移データが不足しています。"

    scores["performance_score"] = s_perf
    details["performance"] = {
        "score": s_perf,
        "max_score": max_perf,
        "value": f"平均売上成長: {f'{rev_growth:+.1f}%' if rev_growth else 'N/A'}",
        "comment": comm_perf
    }

    # -------------------------------------------------------------
    # 5. 財務健全性スコア (Max 15点)
    # -------------------------------------------------------------
    max_safe = MAX_SCORES["safety_score"]
    eq_ratio = financials.get("latest_equity_ratio")
    fcf = financials.get("latest_fcf")
    s_safe = 0

    # 自己資本比率 (Max 8点)
    if eq_ratio is not None:
        if eq_ratio >= FINANCIAL_SAFETY["equity_ratio_excellent"]:
            s_safe += 8
            strengths.append(f"強固な財務基盤 (自己資本比率 {eq_ratio:.1f}%)")
        elif eq_ratio >= FINANCIAL_SAFETY["equity_ratio_good"]:
            s_safe += 6
            strengths.append(f"健全な自己資本比率 ({eq_ratio:.1f}%)")
        elif eq_ratio >= FINANCIAL_SAFETY["equity_ratio_poor"]:
            s_safe += 4
        else:
            s_safe += 1
            risks.append(f"自己資本比率が低い ({eq_ratio:.1f}%)")
    else:
        s_safe += 4

    # フリーキャッシュフロー (Max 7点)
    if fcf is not None:
        if fcf > 0:
            s_safe += 7
            strengths.append("フリーキャッシュフローがプラス（本業の資金創出力あり）")
        else:
            s_safe += 2
            risks.append("直近フリーキャッシュフローがマイナス")
    else:
        s_safe += 4

    scores["safety_score"] = s_safe
    comm_safe = f"自己資本比率: {f'{eq_ratio:.1f}%' if eq_ratio is not None else 'N/A'}, フリーCF: {'プラス' if fcf and fcf > 0 else 'マイナス' if fcf else 'N/A'}"
    details["safety"] = {
        "score": s_safe,
        "max_score": max_safe,
        "value": f"自己資本: {f'{eq_ratio:.1f}%' if eq_ratio is not None else 'N/A'}",
        "comment": comm_safe
    }

    # -------------------------------------------------------------
    # 6. 割安度スコア (Max 10点)
    # -------------------------------------------------------------
    max_val = MAX_SCORES["valuation_score"]
    per = basic.get("per")
    pbr = basic.get("pbr")
    s_val = 0

    # PER (Max 5点)
    if per is not None and per > 0:
        if per <= VALUATION_STANDARDS["per_undervalued"]:
            s_val += 5
            strengths.append(f"PER {per:.1f}倍（割安水準）")
        elif per <= VALUATION_STANDARDS["per_overvalued"]:
            s_val += 3
        else:
            s_val += 1
            risks.append(f"PER {per:.1f}倍（割高水準）")
    else:
        s_val += 2

    # PBR (Max 5点)
    if pbr is not None and pbr > 0:
        if pbr <= VALUATION_STANDARDS["pbr_undervalued"]:
            s_val += 5
            strengths.append(f"PBR {pbr:.2f}倍（1倍割れで資産価値から割安）")
        elif pbr <= VALUATION_STANDARDS["pbr_overvalued"]:
            s_val += 3
        else:
            s_val += 1
    else:
        s_val += 2

    scores["valuation_score"] = s_val
    comm_val = f"PER: {f'{per:.1f}倍' if per else 'N/A'}, PBR: {f'{pbr:.2f}倍' if pbr else 'N/A'}"
    details["valuation"] = {
        "score": s_val,
        "max_score": max_val,
        "value": f"PER: {f'{per:.1f}倍' if per else 'N/A'} / PBR: {f'{pbr:.2f}倍' if pbr else 'N/A'}",
        "comment": comm_val
    }

    # -------------------------------------------------------------
    # 総合スコアとランク判定
    # -------------------------------------------------------------
    total_score = sum(scores.values())

    if total_score >= RANK_THRESHOLDS["S"]:
        rank = "S"
        rank_label = "非常に魅力的（投資適格・トップクラス）"
        rank_badge_color = "#10B981" # Green
    elif total_score >= RANK_THRESHOLDS["A"]:
        rank = "A"
        rank_label = "魅力的（良好な高配当株）"
        rank_badge_color = "#3B82F6" # Blue
    elif total_score >= RANK_THRESHOLDS["B"]:
        rank = "B"
        rank_label = "要警戒・平均的（一部リスクあり）"
        rank_badge_color = "#F59E0B" # Yellow/Amber
    else:
        rank = "C"
        rank_label = "投資非推奨（低利回り・高リスク）"
        rank_badge_color = "#EF4444" # Red

    # 総合診断サマリーコメントの生成
    summary_text = _generate_summary_comment(rank, total_score, basic, strengths, risks)

    return {
        "total_score": total_score,
        "max_total_score": 100,
        "rank": rank,
        "rank_label": rank_label,
        "rank_badge_color": rank_badge_color,
        "scores": scores,
        "details": details,
        "strengths": strengths,
        "risks": risks,
        "summary": summary_text
    }

def _generate_summary_comment(rank: str, total_score: int, basic: dict, strengths: list, risks: list) -> str:
    """総合診断サマリーを文章で生成"""
    name = basic.get("name", "本銘柄")
    y = basic.get("dividend_yield", 0.0)

    if rank == "S":
        return f"{name} は総合スコア {total_score}点（ランクS）と、高配当株として極めて優れた投資適格性を示しています。利回り ({y:.2f}%) の高さに加え、健全な配当性向や強固な財務基盤、非減配の実績が揃っており、長期インカムゲイン投資の主力候補として魅力的です。"
    elif rank == "A":
        return f"{name} は総合スコア {total_score}点（ランクA）と、安定した還元力を持つ魅力的な高配当株です。業績や財務の健全性が高く、ポートフォリオの配当収入を支える銘柄として十分検討に値します。"
    elif rank == "B":
        risk_str = "、".join(risks[:2]) if risks else "指標の一部に改善の余地"
        return f"{name} は総合スコア {total_score}点（ランクB）です。一定の配当は期待できるものの、【{risk_str}】などの懸念点が存在するため、今後の決算動向や業績推移を慎重に注視する必要があります。"
    else:
        risk_str = "、".join(risks[:2]) if risks else "配当水準や業績の課題"
        return f"{name} は総合スコア {total_score}点（ランクC）です。利回りの低さや【{risk_str}】等の要因により、現時点でインカム狙いの高配当株投資としては積極的におすすめできません。"
