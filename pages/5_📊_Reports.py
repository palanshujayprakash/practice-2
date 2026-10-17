"""
Reports & Business Analytics Page (Phase 5)
Plotly interactive charts, daily/monthly sales trends, GST tax slab breakdowns, and Excel workbook exports.
"""
from datetime import date, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from db.schema import init_db
from services.report_service import (
    get_sales_kpis,
    get_daily_sales_data,
    get_top_selling_products,
    get_gst_slab_breakdown,
    export_reports_to_excel,
)
from services.product_service import get_low_stock_products
from utils.currency import format_rupees, paise_to_rupees_decimal
from utils.ui_components import (
    apply_custom_css,
    init_session_state,
    render_page_header,
    render_metric_card,
)

st.set_page_config(page_title="Reports & Analytics - POS", page_icon="📊", layout="wide")
apply_custom_css()
init_session_state()
init_db()

render_page_header(
    title="Analytics & Business Reports",
    subtitle="Track daily revenue velocity, tax collection, top products, and export Excel reports",
    icon="📊"
)

# 1. Date Filter & Export Row
col_df, col_exp = st.columns([2, 1], gap="medium")
with col_df:
    date_filter = st.date_input(
        "Reporting Period",
        value=(date.today() - timedelta(days=30), date.today())
    )

start_date = str(date_filter[0]) if isinstance(date_filter, tuple) and len(date_filter) > 0 else None
end_date = str(date_filter[1]) if isinstance(date_filter, tuple) and len(date_filter) > 1 else start_date

with col_exp:
    st.write("")
    try:
        excel_bytes = export_reports_to_excel(start_date=start_date, end_date=end_date)
        st.download_button(
            label="📥 Export Full Report to Excel (.xlsx)",
            data=excel_bytes,
            file_name=f"pos_report_{start_date}_to_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"Excel export unavailable: {str(e)}")

# 2. Key Performance Indicators (KPIs)
kpis = get_sales_kpis(start_date, end_date)
k1, k2, k3, k4 = st.columns(4)
with k1:
    render_metric_card("Total Revenue", format_rupees(kpis["total_revenue"]), f"{kpis['total_bills']} completed bills")
with k2:
    render_metric_card("Taxable Sales", format_rupees(kpis["total_taxable"]), "Net sales before tax")
with k3:
    render_metric_card("Total GST Collected", format_rupees(kpis["total_gst"]), "CGST + SGST total")
with k4:
    render_metric_card("Total Discounts Given", format_rupees(kpis["total_discount"]), "Store promotional savings")

st.markdown("<br>", unsafe_allow_html=True)

# 3. Interactive Plotly Charts
col_ch1, col_ch2 = st.columns([1.5, 1], gap="large")

with col_ch1:
    st.subheader("📈 Daily Sales Velocity")
    df_daily = get_daily_sales_data(days=30)
    if df_daily.empty:
        st.info("No sales data recorded yet in the last 30 days.")
    else:
        fig_daily = px.bar(
            df_daily,
            x="Date",
            y="Revenue (₹)",
            text_auto=".2s",
            title="Daily Gross Revenue (Last 30 Days)",
            color_discrete_sequence=["#38BDF8"]
        )
        fig_daily.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
        )
        st.plotly_chart(fig_daily, use_container_width=True)

with col_ch2:
    st.subheader("🏆 Top Selling Products")
    df_top = get_top_selling_products(limit=8)
    if df_top.empty:
        st.info("No items sold yet.")
    else:
        fig_top = px.pie(
            df_top,
            values="Quantity Sold",
            names="Item",
            title="Sales Share by Item Volume",
            color_discrete_sequence=px.colors.qualitative.Prism,
            hole=0.4
        )
        fig_top.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_top, use_container_width=True)

st.markdown("---")

# 4. GST Tax Summary Table & Low Stock Alerts
col_t1, col_t2 = st.columns([1.2, 1], gap="large")

with col_t1:
    st.subheader("🏛️ GST Tax Slab Summary")
    df_gst = get_gst_slab_breakdown(start_date, end_date)
    if df_gst.empty:
        st.info("No tax records for this period.")
    else:
        st.dataframe(df_gst, use_container_width=True, hide_index=True)
        tot_cgst = df_gst["CGST (₹)"].sum()
        tot_sgst = df_gst["SGST (₹)"].sum()
        st.caption(f"**Total Tax Liability:** CGST: ₹{tot_cgst:,.2f} | SGST: ₹{tot_sgst:,.2f} | Total: ₹{tot_cgst + tot_sgst:,.2f}")

with col_t2:
    st.subheader("⚠️ Low Stock Inventory Alert")
    low_prods = get_low_stock_products()
    if not low_prods:
        st.success("✅ All products have adequate inventory.")
    else:
        low_table = []
        for it in low_prods:
            low_table.append({
                "Item": it["name"],
                "Stock": f"{it['stock_qty']} {it['unit']}",
                "Min Alert": f"{it['min_stock_qty']} {it['unit']}",
                "Rate": format_rupees(it["selling_price_paise"])
            })
        st.dataframe(pd.DataFrame(low_table), use_container_width=True, hide_index=True)
