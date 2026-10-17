"""
Bill History & Invoice Audit Log Page (Phase 5)
Multi-faceted search, line-item inspection, PDF reprinting, and role-based cancellation with inventory reversal.
"""
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from db.schema import init_db
from services.billing_service import filter_bills, get_bill_details, cancel_bill
from services.customer_service import get_all_customers
from services.pdf_service import generate_bill_pdf
from utils.currency import format_rupees, paise_to_rupees_decimal
from utils.ui_components import apply_custom_css, init_session_state, render_page_header

st.set_page_config(page_title="Bill History - POS", page_icon="📜", layout="wide")
apply_custom_css()
init_session_state()
init_db()

render_page_header(
    title="Invoice History & Audit Trail",
    subtitle="Search past sales, inspect line-item snapshots, reprint PDFs, or cancel invoices",
    icon="📜"
)

# 1. Filter Controls Row
with st.container(border=True):
    st.markdown("#### 🔍 Filter Invoices")
    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([1.5, 1.2, 1, 1, 1.5])

    with col_f1:
        search_txt = st.text_input("Search Bill No or Customer", placeholder="e.g. INV-2026-0001, phone...")

    with col_f2:
        date_range = st.date_input(
            "Date Range",
            value=(date.today() - timedelta(days=30), date.today())
        )

    with col_f3:
        mode_filter = st.selectbox("Payment Mode", options=["All", "cash", "upi", "card", "credit"])

    with col_f4:
        status_filter = st.selectbox("Status", options=["All", "completed", "cancelled"])

    with col_f5:
        customers = get_all_customers()
        cust_map = {"All Customers": None}
        for c in customers:
            cust_map[f"{c['name']} ({c['phone']})"] = c["id"]
        selected_cust_opt = st.selectbox("Filter Customer", options=list(cust_map.keys()))
        selected_cust_id = cust_map[selected_cust_opt]

# Process dates safely
start_d = str(date_range[0]) if isinstance(date_range, tuple) and len(date_range) > 0 else None
end_d = str(date_range[1]) if isinstance(date_range, tuple) and len(date_range) > 1 else start_d

# Query filtered invoices
bills = filter_bills(
    start_date=start_d,
    end_date=end_d,
    customer_id=selected_cust_id,
    payment_mode=mode_filter,
    status=status_filter,
    search_term=search_txt
)

# Top Summary KPIs
total_bills_count = len(bills)
completed_bills = [b for b in bills if b["status"] == "completed"]
total_sales_paise = sum(b["grand_total_paise"] for b in completed_bills)
cancelled_count = len(bills) - len(completed_bills)

k1, k2, k3 = st.columns(3)
with k1:
    st.metric("Total Bills Matching", f"{total_bills_count} Invoices")
with k2:
    st.metric("Net Completed Sales", format_rupees(total_sales_paise))
with k3:
    st.metric("Cancelled Bills", f"{cancelled_count} Invoices")

st.markdown("---")


# 2. Dialog for Invoice Line Item Inspection
@st.dialog("📄 Invoice Inspection & Reprint", width="large")
def show_invoice_dialog(bill_id: int):
    details = get_bill_details(bill_id)
    if not details:
        st.error("Invoice not found.")
        return

    st.markdown(f"### Invoice: `{details['bill_no']}`")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.write(f"**Date:** {details['bill_date']}")
        st.write(f"**Customer:** {details.get('customer_name') or 'Walk-in'}")
        st.write(f"**Contact:** {details.get('customer_phone') or '-'}")
    with col_d2:
        st.write(f"**Payment:** {details['payment_mode'].upper()}")
        status_color = "green" if details['status'] == 'completed' else "red"
        st.markdown(f"**Status:** :{status_color}[{details['status'].upper()}]")
        if details.get("cancellation_reason"):
            st.caption(f"Reason: *{details['cancellation_reason']}*")

    st.markdown("##### Itemized Snapshot at Sale Time")
    item_rows = []
    for it in details.get("items", []):
        item_rows.append({
            "Item Name": it["product_name_snapshot"],
            "Unit Price (₹)": float(paise_to_rupees_decimal(it["unit_price_paise_snapshot"])),
            "Qty": it["quantity"],
            "GST Rate": f"{it['gst_rate_snapshot']}%",
            "GST (₹)": float(paise_to_rupees_decimal(it["gst_amount_paise"])),
            "Total (₹)": float(paise_to_rupees_decimal(it["total_paise"])),
        })
    st.dataframe(pd.DataFrame(item_rows), use_container_width=True, hide_index=True)

    c_s1, c_s2 = st.columns(2)
    with c_s1:
        st.write(f"**Taxable Base:** {format_rupees(details['subtotal_paise'])}")
        st.write(f"**Total GST:** {format_rupees(details['gst_total_paise'])}")
    with c_s2:
        st.write(f"**Discount:** -{format_rupees(details['discount_paise'])}")
        st.markdown(f"#### Grand Total: {format_rupees(details['grand_total_paise'])}")

    st.markdown("---")
    st.markdown("##### 🖨️ Reprint Invoice")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        pdf_80 = generate_bill_pdf(details["bill_no"], paper_size_override="80mm")
        st.download_button(
            "Download 80mm Thermal PDF",
            data=pdf_80,
            file_name=f"{details['bill_no']}_thermal.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    with col_p2:
        pdf_a4 = generate_bill_pdf(details["bill_no"], paper_size_override="A4")
        st.download_button(
            "Download Full A4 PDF",
            data=pdf_a4,
            file_name=f"{details['bill_no']}_A4.pdf",
            mime="application/pdf",
            use_container_width=True
        )


# 3. Dialog for Bill Cancellation
@st.dialog("⚠️ Confirm Invoice Cancellation")
def show_cancellation_dialog(bill_id: int, bill_no: str):
    user = st.session_state.get("user", {})
    if user.get("role") != "owner":
        st.error("🚫 Access Denied: Only Store Owners can cancel invoices. Cashiers cannot cancel bills.")
        return

    st.warning(f"Are you sure you want to cancel invoice **{bill_no}**?")
    st.write("• Product inventory quantities will be automatically **restored**.")
    st.write("• An audit record will be logged in `stock_log`.")
    st.write("• If this was a Credit (Udhaar) sale, the customer debt will be reversed.")

    reason = st.text_input("Cancellation Reason *", placeholder="e.g. Customer returned items, wrong entry")

    if st.button("Confirm Cancellation ❌", type="primary", use_container_width=True):
        if not reason.strip():
            st.error("Please provide a reason for cancellation.")
        else:
            try:
                cancel_bill(bill_id, cancelled_by=user.get("id", 1), reason=reason)
                st.toast(f"✅ Invoice {bill_no} cancelled and stock restored!", icon="🔄")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to cancel invoice: {str(e)}")


# 4. Invoices Table Display
if not bills:
    st.info("No bills found matching your filter criteria.")
else:
    for b in bills:
        with st.container(border=True):
            cb1, cb2, cb3, cb4, cb5, cb6, cb7 = st.columns([1.5, 1.5, 1.5, 1, 1.2, 1, 1])

            with cb1:
                st.markdown(f"**{b['bill_no']}**")
                st.caption(str(b["bill_date"])[:16])

            with cb2:
                cust_disp = b.get("customer_name") or "Walk-in"
                st.write(f"👤 {cust_disp}")
                if b.get("customer_phone"):
                    st.caption(f"📞 {b['customer_phone']}")

            with cb3:
                st.markdown(f"**{format_rupees(b['grand_total_paise'])}**")
                st.caption(f"Tax: {format_rupees(b['gst_total_paise'])}")

            with cb4:
                mode_icons = {"cash": "💵 Cash", "upi": "📱 UPI", "card": "💳 Card", "credit": "📝 Credit"}
                st.write(mode_icons.get(b["payment_mode"], b["payment_mode"]))

            with cb5:
                if b["status"] == "completed":
                    st.markdown("<span class='badge-success'>COMPLETED</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span class='badge-danger'>CANCELLED</span>", unsafe_allow_html=True)
                    if b.get("cancellation_reason"):
                        st.caption(b["cancellation_reason"])

            with cb6:
                if st.button("Details 👁️", key=f"det_{b['id']}", use_container_width=True):
                    show_invoice_dialog(b["id"])

            with cb7:
                if b["status"] == "completed":
                    if st.button("Cancel ❌", key=f"can_{b['id']}", use_container_width=True):
                        show_cancellation_dialog(b["id"], b["bill_no"])
                else:
                    st.button("Cancelled", key=f"can_dis_{b['id']}", disabled=True, use_container_width=True)
