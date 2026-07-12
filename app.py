# ====================== INTRADAY RESULTS SECTION ======================

if df is not None and not df.empty:
    df_sorted = add_sector_column(df)
    section_label("Results")

    # ==================== STRONG BUY & STRONG SELL CARDS ====================
    strong_buy = df_sorted[
        df_sorted["Signal"].str.contains("Strong Buy|Buy", case=False, na=False)
    ]
    strong_sell = df_sorted[
        df_sorted["Signal"].str.contains("Strong Sell|Sell", case=False, na=False)
    ]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #166534, #14532d);
                padding: 25px;
                border-radius: 16px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            ">
                <h2 style="margin:0; font-size:22px;">🟢 STRONG BUY</h2>
                <h1 style="margin:8px 0; font-size:48px; font-weight:700;">{len(strong_buy)}</h1>
                <p style="margin:0; opacity:0.9;">Click below to view all</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("📋 View Strong Buy Stocks", key="btn_strong_buy", use_container_width=True):
            st.session_state.show_strong_buy = True
            st.session_state.show_strong_sell = False

    with col2:
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #991b1b, #7f1d1d);
                padding: 25px;
                border-radius: 16px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            ">
                <h2 style="margin:0; font-size:22px;">🔴 STRONG SELL</h2>
                <h1 style="margin:8px 0; font-size:48px; font-weight:700;">{len(strong_sell)}</h1>
                <p style="margin:0; opacity:0.9;">Click below to view all</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("📋 View Strong Sell Stocks", key="btn_strong_sell", use_container_width=True):
            st.session_state.show_strong_sell = True
            st.session_state.show_strong_buy = False

    # Session state initialization
    if "show_strong_buy" not in st.session_state:
        st.session_state.show_strong_buy = False
    if "show_strong_sell" not in st.session_state:
        st.session_state.show_strong_sell = False

    # ==================== SHOW RESULTS WHEN CARD IS CLICKED ====================
    if st.session_state.show_strong_buy:
        st.markdown("### 🟢 Strong Buy Stocks")
        if not strong_buy.empty:
            render_compact_cards_view(strong_buy)
        else:
            st.info("No Strong Buy signals found in current scan.")

    elif st.session_state.show_strong_sell:
        st.markdown("### 🔴 Strong Sell Stocks")
        if not strong_sell.empty:
            render_compact_cards_view(strong_sell)
        else:
            st.info("No Strong Sell signals found in current scan.")

    # ==================== DEFAULT VIEW (when no card clicked) ====================
    else:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1.4, 1.3, 1.2, 1.3])
            with c1:
                display_mode = st.radio(
                    "Display Mode",
                    ["Top Signals + Clean Table", "Compact Cards", "Full (with Charts)"],
                    horizontal=True,
                    index=0,
                    key="intraday_display_mode",
                )
            with c2:
                if display_mode != "Full (with Charts)":
                    top_n = st.slider("Show top N signals", 5, 35, 12, 1, key="intraday_top_n")
                else:
                    top_n = 0
            with c3:
                hide_charts = st.checkbox("Hide bar charts", value=True, key="intraday_hide_charts")
            with c4:
                only_high_conv = st.checkbox("Only HIGH Conviction", value=False, key="intraday_only_high_conv")

        # Prepare data
        df_to_display = sort_by_priority(df_sorted)

        if only_high_conv:
            df_to_display = df_to_display[
                df_to_display.apply(
                    lambda r: str(r.get("MTF Status", "")).lower() == "confirmed"
                    and abs(float(r.get("Score") or 0)) >= 35,
                    axis=1,
                )
            ]

        if display_mode != "Full (with Charts)" and top_n > 0:
            df_to_display = df_to_display.head(top_n)

        # Render based on mode
        if display_mode == "Top Signals + Clean Table":
            render_compact_table_view(df_to_display, hide_charts=hide_charts)
        elif display_mode == "Compact Cards":
            render_compact_cards_view(df_to_display)
        else:
            render_sector_tabs(df_sorted)

        # Watchlist section
        if watchlist:
            wl_df = df_sorted[df_sorted["Symbol"].isin(watchlist)]
            if not wl_df.empty:
                section_label(f"Watchlist ({len(wl_df)})")
                st.dataframe(sort_by_priority(wl_df), use_container_width=True, hide_index=True)

        # Download button
        st.download_button(
            "Download results CSV",
            sort_by_priority(df_sorted).to_csv(index=False).encode(),
            "scan_results.csv",
            "text/csv",
        )

elif df is not None:
    st.info("No results returned.")
