"""
Customers & Credit (Udhaar) Ledger Page (Phase 5)
Customer directory, purchase history tracking, credit balances, and payment settlements.
"""
import pandas as pd
import streamlit as st
from db.schema import init_db
from services.customer_service import (
    get_customers_with_stats,
    add_customer,
    record_customer_payment,
    update_customer_details,
)
from services.billing_service import filter_bills
from utils.currency import format_rupees, paise_to_rupees_decimal, rupees_to_paise
from utils.ui_components import (
    apply_custom_css,
    init_session_state,
    render_page_header,
    render_metric_card,
)

st.set_page_config(page_title="Customers & Udhaar - POS", page_icon="👥", layout="wide")
apply_custom_css()
init_session_state()
init_db()

render_page_header(
    title="Customer Directory & Credit (Udhaar) Ledger",
    subtitle="Track customer purchase history, outstanding credit balances, and record payments",
    icon="👥"
)

# Fetch customer stats
customers = get_customers_with_stats()

total_customers = len(customers)
total_udhaar_paise = sum(c["credit_balance_paise"] for c in customers)
total_lifetime_sales_paise = sum(c["total_spent_paise"] for c in customers)

# Top KPI Metric Cards
c1, c2, c3 = st.columns(3)
with c1:
    render_metric_card("Registered Customers", f"{total_customers:,} People", "Active customer accounts")
with c2:
    badge = "⚠️ Collect Udhaar" if total_udhaar_paise > 0 else "✅ No Pending Dues"
    render_metric_card("Total Pending Udhaar", format_rupees(total_udhaar_paise), badge)
with c3:
    render_metric_card("Customer Lifetime Purchases", format_rupees(total_lifetime_sales_paise), "Completed invoice volume")

st.markdown("<br>", unsafe_allow_html=True)


# Settle Payment Dialog
@st.dialog("💵 Record Udhaar (Credit) Settlement")
def show_payment_dialog(customer_id: int, customer_name: str, current_balance_paise: int):
    st.markdown(f"#### Customer: **{customer_name}**")
    st.write(f"Current Outstanding Udhaar: **{format_rupees(current_balance_paise)}**")

    with st.form("settlement_form", clear_on_submit=True):
        pay_rs = st.number_input(
            "Amount Received (₹) *",
            min_value=1.0,
            value=float(paise_to_rupees_decimal(current_balance_paise)),
            step=10.0,
            format="%.2f"
        )
        pay_mode = st.selectbox("Payment Mode", options=["Cash", "UPI", "Bank Transfer", "Cheque"])
        notes = st.text_input("Remarks / Transaction Ref", placeholder="e.g. GPay ref 1234, cash received by owner")

        submitted = st.form_submit_button("💾 Save Payment Receipt", type="primary", use_container_width=True)
        if submitted:
            try:
                pay_paise = rupees_to_paise(pay_rs)
                record_customer_payment(customer_id, pay_paise, payment_mode=pay_mode.lower(), notes=notes)
                st.toast(f"✅ Received {format_rupees(pay_paise)} from {customer_name}!", icon="🎉")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to record payment: {str(e)}")


# Customer Invoices Dialog
@st.dialog("📜 Customer Purchase History", width="large")
def show_customer_bills_dialog(customer_id: int, customer_name: str):
    st.markdown(f"#### Invoices for: **{customer_name}**")
    cust_bills = filter_bills(customer_id=customer_id)
    if not cust_bills:
        st.info("No invoices found for this customer.")
        return

    b_rows = []
    for b in cust_bills:
        b_rows.append({
            "Bill No": b["bill_no"],
            "Date": str(b["bill_date"])[:16],
            "Payment Mode": b["payment_mode"].upper(),
            "Total (₹)": float(paise_to_rupees_decimal(b["grand_total_paise"])),
            "Status": b["status"].upper(),
        })
    st.dataframe(pd.DataFrame(b_rows), use_container_width=True, hide_index=True)


# Tabs: Customer Directory vs Add Customer
tab_dir, tab_add_c = st.tabs(["📋 Customer Directory & Udhaar Ledger", "➕ Register New Customer"])

with tab_dir:
    col_s1, col_s2 = st.columns([2, 1])
    with col_s1:
        c_search = st.text_input("🔍 Search Customers", placeholder="Search by customer name or phone number...")
    with col_s2:
        only_credit = st.checkbox("Show Only Customers with Pending Udhaar", value=False)

    filtered_custs = get_customers_with_stats(search_term=c_search)
    if only_credit:
        filtered_custs = [c for c in filtered_custs if c["credit_balance_paise"] > 0]

    if not filtered_custs:
        st.info("No customers found.")
    else:
        for c in filtered_custs:
            with st.container(border=True):
                col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1.2, 1.2])

                with col1:
                    st.markdown(f"**{c['name']}**")
                    st.caption(f"📞 {c['phone']} | {c.get('address') or 'No address'}")

                with col2:
                    st.write(f"Total Purchases:")
                    st.markdown(f"**{format_rupees(c['total_spent_paise'])}** ({c['total_bills_count']} bills)")

                with col3:
                    st.write("Pending Udhaar:")
                    if c["credit_balance_paise"] > 0:
                        st.markdown(f"<span class='badge-danger'>{format_rupees(c['credit_balance_paise'])}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span class='badge-success'>₹ 0.00 (Clear)</span>", unsafe_allow_html=True)

                with col4:
                    if st.button("History 📜", key=f"hist_{c['id']}", use_container_width=True):
                        show_customer_bills_dialog(c["id"], c["name"])

                with col5:
                    if c["credit_balance_paise"] > 0:
                        if st.button("Settle 💵", key=f"set_{c['id']}", type="primary", use_container_width=True):
                            show_payment_dialog(c["id"], c["name"], c["credit_balance_paise"])
                    else:
                        st.button("Paid ✅", key=f"set_dis_{c['id']}", disabled=True, use_container_width=True)

with tab_add_c:
    st.subheader("Add New Customer")
    with st.form("new_customer_form", clear_on_submit=True):
        col_nc1, col_nc2 = st.columns(2)
        with col_nc1:
            nc_name = st.text_input("Customer Name *", placeholder="e.g. Rajesh Kumar")
            nc_phone = st.text_input("Mobile Phone *", placeholder="e.g. 9876543210")
        with col_nc2:
            nc_address = st.text_area("Address (Optional)", placeholder="House no, street, locality...")

        nc_submit = st.form_submit_button("➕ Register Customer", type="primary", use_container_width=True)
        if nc_submit:
            if not nc_name.strip() or not nc_phone.strip():
                st.error("Name and Phone are mandatory.")
            else:
                try:
                    c_new_id = add_customer(nc_name, nc_phone, nc_address)
                    st.toast(f"✅ Customer '{nc_name}' registered successfully! (ID: {c_new_id})", icon="👥")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add customer: {str(e)}")
