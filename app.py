"""
高配当株分析＆魅力度判定 Webアプリケーション (Streamlit)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import stock_search
import stock_fetcher
import stock_analyzer
import config

# ページ設定
st.set_page_config(
    page_title="高配当株 分析＆魅力度チェッカー",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS（フォントやカードスタイルの調整）
st.markdown("""
<style>
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .badge-S {
        background-color: #10B981;
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.1rem;
        display: inline-block;
    }
    .badge-A {
        background-color: #3B82F6;
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.1rem;
        display: inline-block;
    }
    .badge-B {
        background-color: #F59E0B;
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.1rem;
        display: inline-block;
    }
    .badge-C {
        background-color: #EF4444;
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.1rem;
        display: inline-block;
    }
    .score-number {
        font-size: 2.8rem;
        font-weight: 800;
        line-height: 1;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# サイドバー
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("💡 ガイド＆判定基準")
    st.markdown("""
    株式番号（4桁コード）または会社名を入力すると、過去の決算や配当金推移から**高配当株としての投資適格性**を多角的に診断します。
    """)
    
    st.subheader("📊 判定基準（100点満点）")
    st.markdown("""
    - **① 配当利回り (20点)**: 3.5%~4%以上を高評価
    - **② 配当性向 (20点)**: 30%~60%が健全、100%超は危険
    - **③ 配当継続力 (20点)**: 過去の非減配・連続増配実績
    - **④ 業績安定性 (15点)**: 継続黒字、売上・利益の成長
    - **⑤ 財務健全性 (15点)**: 自己資本比率、フリーCF
    - **⑥ 割安度 (10点)**: PER、PBR水準
    """)

    st.subheader("🎯 ランク基準")
    st.markdown("""
    - <span class="badge-S">S ランク</span> 85点以上: 極めて魅力的
    - <span class="badge-A">A ランク</span> 70~84点: 魅力的
    - <span class="badge-B">B ランク</span> 50~69点: 平均・要警戒
    - <span class="badge-C">C ランク</span> 50点未満: 投資非推奨
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown("**⚡ クイック銘柄チェック**")
    quick_stocks = [
        ("三菱商事 (8058)", "8058"),
        ("トヨタ自動車 (7203)", "7203"),
        ("JT (2914)", "2914"),
        ("KDDI (9433)", "9433"),
        ("コカ・コーラ (KO)", "KO"),
        ("アップル (AAPL)", "AAPL"),
    ]
    for label, code in quick_stocks:
        if st.button(label, use_container_width=True, key=f"quick_{code}"):
            st.session_state["search_input"] = code
            st.session_state["trigger_search"] = True

    st.divider()
    st.caption("※ 本ソフトは投資助言を行うものではありません。投資判断はご自身の責任で行ってください。")

# -----------------------------------------------------------------------------
# メイン画面ヘッダー
# -----------------------------------------------------------------------------
st.title("📈 高配当株 分析＆魅力度チェッカー")
st.caption("株式コード（8058等）または企業名（トヨタ、三菱商事、任天堂等）を入力して検索")

# 検索入力セクション
col_input, col_btn = st.columns([4, 1])

if "search_input" not in st.session_state:
    st.session_state["search_input"] = "8058"

with col_input:
    query = st.text_input(
        "証券コード または 会社名",
        value=st.session_state["search_input"],
        placeholder="例: 8058, 7203, トヨタ, 三菱商事, 任天堂, KO, AAPL",
        label_visibility="collapsed"
    )

with col_btn:
    search_clicked = st.button("銘柄を分析 🔍", type="primary", use_container_width=True)

trigger = search_clicked or st.session_state.get("trigger_search", False)
if st.session_state.get("trigger_search", False):
    st.session_state["trigger_search"] = False

# -----------------------------------------------------------------------------
# 検索および銘柄特定処理
# -----------------------------------------------------------------------------
if query:
    norm_q = stock_search.normalize_input(query)

    # 検索候補の取得
    with st.spinner("銘柄情報を検索中..."):
        candidates = stock_search.search_stocks(norm_q, max_results=5)

    if not candidates:
        st.error(f"「{query}」に一致する銘柄が見つかりませんでした。証券コード（4桁）または会社名を正しく入力してください。")
        st.stop()

    # 候補が複数あり、かつ完全一致のコードではない場合
    selected_candidate = candidates[0]
    if len(candidates) > 1 and not (len(norm_q) == 4 and norm_q.isdigit()):
        options = {f"{c['name']} ({c['symbol']}) - {c.get('market', '')}": c for c in candidates}
        selected_label = st.selectbox("検索候補から選択してください:", list(options.keys()))
        selected_candidate = options[selected_label]

    symbol = selected_candidate["symbol"]

    # -------------------------------------------------------------------------
    # データ取得
    # -------------------------------------------------------------------------
    with st.spinner(f"{selected_candidate['name']} ({symbol}) の決算・配当データを取得中..."):
        stock_data = stock_fetcher.fetch_stock_data(symbol)
        analysis = stock_analyzer.analyze_stock(stock_data)

    basic = stock_data["basic_info"]
    div_df = stock_data["dividend_df"]
    financials = stock_data["financials"]

    # -------------------------------------------------------------------------
    # 企業ヘッダーサマリー
    # -------------------------------------------------------------------------
    st.markdown("---")
    head_col1, head_col2, head_col3, head_col4 = st.columns([3, 2, 2, 2])

    with head_col1:
        st.subheader(f"{basic['name']}")
        st.caption(f"コード: **{basic['symbol']}** | 市場: {basic.get('sector', '')} / {basic.get('industry', '')}")

    with head_col2:
        currency = "円" if basic["currency"] == "JPY" else "$"
        st.metric(
            label="現在株価",
            value=f"{basic['current_price']:,.1f} {currency}",
            delta=f"{basic['price_change']:+,.1f} ({basic['price_change_pct']:+.2f}%)"
        )

    with head_col3:
        st.metric(
            label="配当利回り (予想)",
            value=f"{basic['dividend_yield']:.2f}%",
            delta="高利回り" if basic['dividend_yield'] >= 3.5 else "標準" if basic['dividend_yield'] >= 2.5 else "控えめ",
            delta_color="normal" if basic['dividend_yield'] >= 3.5 else "off"
        )

    with head_col4:
        payout_display = f"{basic['payout_ratio']:.1f}%" if basic['payout_ratio'] is not None else "N/A"
        st.metric(
            label="配当性向",
            value=payout_display,
            delta="健全" if (basic['payout_ratio'] and 30 <= basic['payout_ratio'] <= 60) else "要注視" if basic['payout_ratio'] else None,
            delta_color="normal" if (basic['payout_ratio'] and 30 <= basic['payout_ratio'] <= 60) else "inverse"
        )

    # -------------------------------------------------------------------------
    # 総合診断カード（スコア・ランク・総評・強み・注意点）
    # -------------------------------------------------------------------------
    st.markdown("### 🏆 総合魅力度診断結果")
    
    score_col, summary_col = st.columns([1, 2])

    with score_col:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1e293b, #0f172a); color: white; padding: 24px; border-radius: 12px; text-align: center;">
            <div style="font-size: 1rem; color: #94a3b8; margin-bottom: 8px;">総合魅力度スコア</div>
            <div class="score-number" style="color: {analysis['rank_badge_color']};">{analysis['total_score']} <span style="font-size: 1.2rem; color: #94a3b8;">/ 100</span></div>
            <div style="margin-top: 14px;">
                <span class="badge-{analysis['rank']}">ランク {analysis['rank']}</span>
            </div>
            <div style="margin-top: 8px; font-size: 0.95rem; font-weight: bold; color: #e2e8f0;">{analysis['rank_label']}</div>
        </div>
        """, unsafe_allow_html=True)

    with summary_col:
        st.info(f"**【診断総評】**\n\n{analysis['summary']}")
        
        c_str, c_risk = st.columns(2)
        with c_str:
            st.markdown("**✅ 評価ポイント・強み**")
            if analysis["strengths"]:
                for s in analysis["strengths"]:
                    st.markdown(f"- <span style='color: #10B981;'>✔</span> {s}", unsafe_allow_html=True)
            else:
                st.markdown("- 特筆すべき強み指標なし")

        with c_risk:
            st.markdown("**⚠️ 警戒すべき注意点・リスク**")
            if analysis["risks"]:
                for r in analysis["risks"]:
                    st.markdown(f"- <span style='color: #EF4444;'>⚠</span> {r}", unsafe_allow_html=True)
            else:
                st.markdown("- 現状、重大な警告指標はありません")

    # -------------------------------------------------------------------------
    # 6大指標の詳細スコア ＆ レーダーチャート
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("📊 6大指標の個別評価")

    radar_col, bar_col = st.columns([1, 1])

    with radar_col:
        # レーダーチャート
        categories = ["配当利回り", "配当性向", "増配力・継続性", "業績安定性", "財務健全性", "割安度"]
        details = analysis["details"]
        current_scores = [
            details["yield"]["score"] / details["yield"]["max_score"] * 100,
            details["payout"]["score"] / details["payout"]["max_score"] * 100,
            details["history"]["score"] / details["history"]["max_score"] * 100,
            details["performance"]["score"] / details["performance"]["max_score"] * 100,
            details["safety"]["score"] / details["safety"]["max_score"] * 100,
            details["valuation"]["score"] / details["valuation"]["max_score"] * 100,
        ]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=current_scores + [current_scores[0]],
            theta=categories + [categories[0]],
            fill='toself',
            name=basic['name'],
            line_color=analysis['rank_badge_color'],
            fillcolor=analysis['rank_badge_color'] + "33"
        ))
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100])
            ),
            showlegend=False,
            margin=dict(l=40, r=40, t=20, b=20),
            height=320
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    with bar_col:
        # プログレスバー形式で表示
        items_map = [
            ("① 配当利回り", "yield"),
            ("② 減配リスク (配当性向)", "payout"),
            ("③ 配当継続力・増配実績", "history"),
            ("④ 業績・収益の安定性", "performance"),
            ("⑤ 財務健全性 (自己資本・CF)", "safety"),
            ("⑥ 割安度 (PER・PBR)", "valuation"),
        ]
        for title, key in items_map:
            d = details[key]
            sc = d["score"]
            m_sc = d["max_score"]
            ratio = sc / m_sc
            st.markdown(f"**{title}**: `{sc} / {m_sc}点` （{d['value']}）")
            st.progress(ratio)
            st.caption(d["comment"])

    # -------------------------------------------------------------------------
    # タブ別 詳細チャート & データ
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("🔍 詳細分析データ")

    tab_div, tab_perf, tab_fin, tab_info = st.tabs([
        "💰 配当金推移", "📈 業績推移 (売上・利益)", "🛡️ 財務・キャッシュフロー", "📋 指標一覧・企業概要"
    ])

    # -------------------------------------------------------------------------
    # タブ1: 配当金推移
    # -------------------------------------------------------------------------
    with tab_div:
        if div_df is not None and not div_df.empty:
            c1, c2 = st.columns([2, 1])
            with c1:
                # 配当金棒グラフ
                color_map = {"増配": "#10B981", "維持": "#3B82F6", "減配": "#EF4444", "初回/基準": "#6B7280"}
                fig_div = px.bar(
                    div_df,
                    x="year",
                    y="dividend",
                    color="status",
                    color_discrete_map=color_map,
                    title="過去の年間1株当たり配当金推移",
                    labels={"year": "年度", "dividend": f"年間配当金 ({currency})", "status": "前年比状態"},
                    text="dividend"
                )
                fig_div.update_layout(xaxis=dict(tickmode="linear", dtick=1))
                st.plotly_chart(fig_div, use_container_width=True)

            with c2:
                st.markdown("**年度別配当データ一覧**")
                display_div = div_df.copy()
                display_div.columns = ["年度", f"配当金 ({currency})", "増減率(%)", "判定"]
                st.dataframe(display_div, hide_index=True, use_container_width=True)
        else:
            st.info("配当金推移の詳細履歴データがありません。")

    # -------------------------------------------------------------------------
    # タブ2: 業績推移
    # -------------------------------------------------------------------------
    with tab_perf:
        history = financials.get("history", [])
        if history:
            perf_df = pd.DataFrame(history)
            
            # 売上高と純利益のグラフ
            fig_perf = go.Figure()
            if "revenue" in perf_df and perf_df["revenue"].notna().any():
                fig_perf.add_trace(go.Bar(
                    x=perf_df["date"],
                    y=perf_df["revenue"] / 1e8 if currency == "円" else perf_df["revenue"] / 1e6,
                    name=f"売上高 ({'億円' if currency == '円' else '百万$'})",
                    marker_color="#93C5FD"
                ))
            if "operating_income" in perf_df and perf_df["operating_income"].notna().any():
                fig_perf.add_trace(go.Bar(
                    x=perf_df["date"],
                    y=perf_df["operating_income"] / 1e8 if currency == "円" else perf_df["operating_income"] / 1e6,
                    name=f"営業利益 ({'億円' if currency == '円' else '百万$'})",
                    marker_color="#3B82F6"
                ))
            if "net_income" in perf_df and perf_df["net_income"].notna().any():
                fig_perf.add_trace(go.Bar(
                    x=perf_df["date"],
                    y=perf_df["net_income"] / 1e8 if currency == "円" else perf_df["net_income"] / 1e6,
                    name=f"当期純利益 ({'億円' if currency == '円' else '百万$'})",
                    marker_color="#10B981"
                ))

            fig_perf.update_layout(
                barmode="group",
                title="過去数年の業績推移（売上高・営業利益・純利益）",
                xaxis_title="決算年月",
                yaxis_title=f"金額 ({'億円' if currency == '円' else '百万$'})",
                height=380
            )
            st.plotly_chart(fig_perf, use_container_width=True)

            # EPS推移
            if "eps" in perf_df and perf_df["eps"].notna().any():
                fig_eps = px.line(
                    perf_df,
                    x="date",
                    y="eps",
                    markers=True,
                    title="1株当たり利益 (EPS) 推移",
                    labels={"date": "決算年月", "eps": f"EPS ({currency})"}
                )
                st.plotly_chart(fig_eps, use_container_width=True)
        else:
            st.info("過去の決算業績データがありません。")

    # -------------------------------------------------------------------------
    # タブ3: 財務・キャッシュフロー
    # -------------------------------------------------------------------------
    with tab_fin:
        history = financials.get("history", [])
        if history:
            fin_df = pd.DataFrame(history)
            
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                if "equity_ratio" in fin_df and fin_df["equity_ratio"].notna().any():
                    fig_eq = px.line(
                        fin_df,
                        x="date",
                        y="equity_ratio",
                        markers=True,
                        title="自己資本比率の推移 (%)",
                        labels={"date": "決算年月", "equity_ratio": "自己資本比率 (%)"}
                    )
                    fig_eq.add_hline(y=50, line_dash="dash", line_color="green", annotation_text="目安 50%")
                    st.plotly_chart(fig_eq, use_container_width=True)
                else:
                    st.info("自己資本比率の履歴データがありません。")

            with c_f2:
                if "operating_cf" in fin_df and "free_cf" in fin_df:
                    fig_cf = go.Figure()
                    fig_cf.add_trace(go.Bar(
                        x=fin_df["date"],
                        y=fin_df["operating_cf"] / 1e8 if currency == "円" else fin_df["operating_cf"] / 1e6,
                        name=f"営業CF ({'億円' if currency == '円' else '百万$'})",
                        marker_color="#6EE7B7"
                    ))
                    fig_cf.add_trace(go.Bar(
                        x=fin_df["date"],
                        y=fin_df["free_cf"] / 1e8 if currency == "円" else fin_df["free_cf"] / 1e6,
                        name=f"フリーCF ({'億円' if currency == '円' else '百万$'})",
                        marker_color="#059669"
                    ))
                    fig_cf.update_layout(
                        barmode="group",
                        title="営業キャッシュフロー ＆ フリーキャッシュフロー推移",
                        xaxis_title="決算年月",
                        yaxis_title=f"金額 ({'億円' if currency == '円' else '百万$'})"
                    )
                    st.plotly_chart(fig_cf, use_container_width=True)
        else:
            st.info("キャッシュフロー・財務データがありません。")

    # -------------------------------------------------------------------------
    # タブ4: 指標一覧・企業概要
    # -------------------------------------------------------------------------
    with tab_info:
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown("**📊 バリュエーション＆主要指標**")
            m_cap = basic['market_cap']
            if m_cap:
                m_cap_str = f"{m_cap / 1e12:.2f} 兆円" if currency == "円" else f"{m_cap / 1e9:.2f} B$"
            else:
                m_cap_str = "N/A"

            metrics_table = [
                {"指標": "現在株価", "値": f"{basic['current_price']:,.1f} {currency}"},
                {"指標": "配当利回り (予想)", "値": f"{basic['dividend_yield']:.2f}%"},
                {"指標": "1株当たり年間配当", "値": f"{basic['dividend_rate']:.1f} {currency}"},
                {"指標": "配当性向", "値": f"{basic['payout_ratio']:.1f}%" if basic['payout_ratio'] else "N/A"},
                {"指標": "PER (株価収益率)", "値": f"{basic['per']:.1f}倍" if basic['per'] else "N/A"},
                {"指標": "PBR (純資産倍率)", "値": f"{basic['pbr']:.2f}倍" if basic['pbr'] else "N/A"},
                {"指標": "ROE (自己資本利益率)", "値": f"{basic['roe']:.1f}%" if basic['roe'] else "N/A"},
                {"指標": "時価総額", "値": m_cap_str},
            ]
            st.dataframe(pd.DataFrame(metrics_table), hide_index=True, use_container_width=True)

        with col_t2:
            st.markdown("**🏢 企業概要・事業内容**")
            st.write(basic["summary"])
