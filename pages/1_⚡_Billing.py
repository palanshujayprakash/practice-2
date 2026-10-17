"""
High-Speed Billing & POS Terminal Page (Phase 3 Core)
Optimized for barcode scanning, rapid keyboard entry, live cart calculation, and atomic checkout.
"""
import streamlit as st
import pandas as pd
from db.schema import init_db
from services.product_service import (
    get_all_products,
    get_product_by_barcode,
    get_product_by_id,
)
from services.customer_service import (
    get_all_customers,
    get_customer_by_phone,
    add_customer,
)
from services.billing_service import (
    calculate_cart_summary,
    checkout_bill,
)
from services.settings_service import get_shop_settings
from services.upi_service import generate_upi_qr_bytes, build_upi_url
from services.pdf_service import generate_bill_pdf
from utils.currency import format_rupees, paise_to_rupees_decimal, rupees_to_paise
from utils.ui_components import (
    apply_custom_css,
    init_session_state,
    render_page_header,
)

# 1. Page Config & CSS
st.set_page_config(page_title="Billing Terminal - POS", page_icon="⚡", layout="wide")
apply_custom_css()
init_session_state()
init_db()

render_page_header(
    title="⚡ Fast Billing & POS Checkout",
    subtitle="Scan barcode or type item name, adjust quantities, and print invoice",
    icon=""
)

# Ensure session state variables
if "cart" not in st.session_state:
    st.session_state.cart = []
if "last_completed_bill" not in st.session_state:
    st.session_state.last_completed_bill = None
if "selected_customer_id" not in st.session_state:
    st.session_state.selected_customer_id = None
if "discount_type" not in st.session_state:
    st.session_state.discount_type = "Fixed (₹)"
if "discount_val" not in st.session_state:
    st.session_state.discount_val = 0.0

# Pre-fetch catalog and customers
all_products = get_all_products(active_only=True)
all_customers = get_all_customers()

@st.dialog("📱 Scan & Pay via UPI")
def open_upi_qr_modal(amount_paise: int, qr_img_bytes: bytes, payee: str, upi_vpa: str):
    """Customer-facing full size QR code dialog modal."""
    st.markdown(
        f"""
        <div style="text-align: center; padding: 12px; background: rgba(15, 23, 42, 0.7); border-radius: 12px; border: 1px solid #334155; margin-bottom: 12px;">
            <div style="font-size: 0.85rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px;">Amount Payable</div>
            <div style="font-size: 2.4rem; font-weight: 800; color: #38BDF8; margin: 4px 0;">{format_rupees(amount_paise)}</div>
            <div style="font-size: 0.95rem; color: #F8FAFC;">Pay to: <b>{payee}</b></div>
            <div style="font-size: 0.85rem; color: #38BDF8; margin-top: 2px;">UPI ID: <code>{upi_vpa}</code></div>
        </div>
        """,
        unsafe_allow_html=True
    )
    col1, col2, col3 = st.columns([0.5, 4, 0.5])
    with col2:
        st.image(qr_img_bytes, width=280)
    st.markdown(
        """
        <div style="text-align: center; color: #94A3B8; font-size: 0.85rem; margin-top: 8px;">
            Supports <b>Google Pay</b>, <b>PhonePe</b>, <b>Paytm</b>, <b>BHIM</b>, <b>Cred</b> &amp; all bank UPI apps.
        </div>
        """,
        unsafe_allow_html=True
    )


# Top Checkout Split Layout
col_cart, col_checkout = st.columns([1.75, 1], gap="medium")

# -------------------------------------------------------------------
# LEFT COLUMN: BARCODE / SEARCH INPUT & CART TABLE
# -------------------------------------------------------------------
with col_cart:
    # 1. Rapid Barcode / Search Box
    with st.form("barcode_scan_form", clear_on_submit=True):
        f_scan, f_btn = st.columns([3.5, 1])
        with f_scan:
            scan_input = st.text_input(
                "Scan Barcode or Search Item",
                placeholder="Scan barcode or type exact product name and press Enter...",
                label_visibility="collapsed",
                key="scan_input_box"
            )
        with f_btn:
            scan_submitted = st.form_submit_button("⚡ Add to Cart", type="primary", use_container_width=True)

        if scan_submitted and scan_input.strip():
            query = scan_input.strip()
            # Try exact barcode match first
            found_prod = get_product_by_barcode(query)
            if not found_prod:
                # Try exact name match or fuzzy find
                matches = [p for p in all_products if query.lower() in p["name"].lower()]
                if matches:
                    found_prod = matches[0]

            if not found_prod:
                st.toast(f"❌ Item not found: '{query}'", icon="🔍")
            else:
                # Check if item already exists in cart
                existing = next((i for i in st.session_state.cart if i["id"] == found_prod["id"]), None)
                if existing:
                    existing["quantity"] += 1
                    st.toast(f"➕ Incremented {found_prod['name']} (Qty: {existing['quantity']})", icon="⚡")
                else:
                    if found_prod["stock_qty"] <= 0:
                        st.toast(f"⚠️ Warning: '{found_prod['name']}' is out of stock!", icon="⚠️")
                    st.session_state.cart.append({
                        "id": found_prod["id"],
                        "name": found_prod["name"],
                        "selling_price_paise": found_prod["selling_price_paise"],
                        "unit": found_prod["unit"],
                        "gst_rate": found_prod["gst_rate"],
                        "quantity": 1.0,
                        "stock_qty": found_prod["stock_qty"]
                    })
                    st.toast(f"🛒 Added '{found_prod['name']}' to cart", icon="✅")
                st.rerun()

    # Quick Mouse Dropdown Selector
    with st.expander("🔎 Or Select Product from Dropdown Catalog", expanded=False):
        c_sel, c_qty, c_add = st.columns([3, 1, 1])
        with c_sel:
            prod_options = {f"{p['name']} ({p['barcode'] or 'No Barcode'}) - {format_rupees(p['selling_price_paise'])}": p for p in all_products}
            selected_label = st.selectbox("Choose Product", options=list(prod_options.keys()) if prod_options else ["No products available"], label_visibility="collapsed")
        with c_qty:
            sel_qty = st.number_input("Qty", min_value=1.0, value=1.0, step=1.0, label_visibility="collapsed")
        with c_add:
            if st.button("Add Item", use_container_width=True):
                if prod_options and selected_label in prod_options:
                    p_chosen = prod_options[selected_label]
                    existing = next((i for i in st.session_state.cart if i["id"] == p_chosen["id"]), None)
                    if existing:
                        existing["quantity"] += sel_qty
                    else:
                        st.session_state.cart.append({
                            "id": p_chosen["id"],
                            "name": p_chosen["name"],
                            "selling_price_paise": p_chosen["selling_price_paise"],
                            "unit": p_chosen["unit"],
                            "gst_rate": p_chosen["gst_rate"],
                            "quantity": float(sel_qty),
                            "stock_qty": p_chosen["stock_qty"]
                        })
                    st.rerun()

    st.markdown("---")

    # 2. Cart Table Listing
    if not st.session_state.cart:
        st.info("🛒 Cart is empty. Scan barcodes or select products to begin sale.")
    else:
        st.markdown(f"#### 🛒 Current Bill Items ({len(st.session_state.cart)} distinct item(s))")

        # Cart Table Header
        h1, h2, h3, h4, h5, h6 = st.columns([3, 1.2, 1.2, 1, 1.3, 0.6])
        h1.caption("**ITEM NAME**")
        h2.caption("**RATE (₹)**")
        h3.caption("**QTY**")
        h4.caption("**GST**")
        h5.caption("**TOTAL (₹)**")
        h6.caption("**DEL**")

        cart_to_remove = []

        for idx, item in enumerate(st.session_state.cart):
            col_name, col_rate, col_qty, col_gst, col_total, col_del = st.columns([3, 1.2, 1.2, 1, 1.3, 0.6])

            with col_name:
                st.write(f"**{item['name']}**")
                if item["quantity"] > item["stock_qty"]:
                    st.markdown("<span class='badge-danger'>Exceeds Stock!</span>", unsafe_allow_html=True)

            with col_rate:
                st.write(format_rupees(item["selling_price_paise"]))

            with col_qty:
                new_q = st.number_input(
                    f"Qty_{idx}",
                    min_value=0.1,
                    value=float(item["quantity"]),
                    step=1.0,
                    key=f"cart_qty_{item['id']}_{idx}",
                    label_visibility="collapsed"
                )
                if new_q != item["quantity"]:
                    item["quantity"] = new_q
                    st.rerun()

            with col_gst:
                st.write(f"{item['gst_rate']}%")

            with col_total:
                line_total = int(item["selling_price_paise"] * item["quantity"])
                st.write(format_rupees(line_total))

            with col_del:
                if st.button("🗑️", key=f"del_{item['id']}_{idx}", help="Remove from cart"):
                    cart_to_remove.append(idx)

        if cart_to_remove:
            for r_idx in sorted(cart_to_remove, reverse=True):
                st.session_state.cart.pop(r_idx)
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        col_clr, _ = st.columns([1, 3])
        with col_clr:
            if st.button("🧹 Clear Cart", type="secondary", use_container_width=True):
                st.session_state.cart = []
                st.rerun()


# -------------------------------------------------------------------
# RIGHT COLUMN: CUSTOMER, DISCOUNT, TOTALS & CHECKOUT
# -------------------------------------------------------------------
with col_checkout:
    st.subheader("Invoice Summary")

    # 1. Customer Section
    cust_options = {"None (Walk-in Customer)": None}
    for c in all_customers:
        bal_str = f" [Udhaar: {format_rupees(c['credit_balance_paise'])}]" if c["credit_balance_paise"] > 0 else ""
        cust_options[f"{c['name']} ({c['phone']}){bal_str}"] = c["id"]

    selected_cust_label = st.selectbox(
        "👤 Customer",
        options=list(cust_options.keys()),
        index=0
    )
    current_customer_id = cust_options[selected_cust_label]

    # Quick Add Customer expander
    with st.expander("➕ Quick Add New Customer", expanded=False):
        with st.form("quick_add_customer_form", clear_on_submit=True):
            qc_name = st.text_input("Customer Name *")
            qc_phone = st.text_input("Mobile Phone *")
            qc_submit = st.form_submit_button("Save Customer", use_container_width=True)
            if qc_submit:
                if not qc_name.strip() or not qc_phone.strip():
                    st.error("Name and Phone are required.")
                else:
                    try:
                        new_c_id = add_customer(qc_name, qc_phone)
                        st.toast(f"✅ Customer '{qc_name}' added!", icon="👤")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    st.markdown("---")

    # 2. Discount Box
    cd1, cd2 = st.columns([1, 1.2])
    with cd1:
        st.session_state.discount_type = st.selectbox(
            "Discount Type",
            options=["Fixed (₹)", "Percentage (%)"],
            index=0 if st.session_state.discount_type == "Fixed (₹)" else 1
        )
    with cd2:
        st.session_state.discount_val = st.number_input(
            "Discount Value",
            min_value=0.0,
            value=float(st.session_state.discount_val),
            step=5.0 if st.session_state.discount_type == "Fixed (₹)" else 1.0
        )

    # Calculate summary
    summary = calculate_cart_summary(
        st.session_state.cart,
        st.session_state.discount_type,
        st.session_state.discount_val
    )

    # 3. Financial Breakdown Card
    with st.container(border=True):
        st.write(f"**Gross Amount:** {format_rupees(summary['gross_total_paise'])}")
        st.write(f"**Taxable Base:** {format_rupees(summary['subtotal_paise'])}")
        st.write(f"**Total GST Tax:** {format_rupees(summary['gst_total_paise'])}")
        if summary["discount_paise"] > 0:
            st.write(f"**Discount Applied:** -{format_rupees(summary['discount_paise'])}")
        st.markdown("---")
        st.markdown(
            f"""
            <div style="font-size: 1.6rem; font-weight: 800; color: #38BDF8; margin-bottom: 0.5rem;">
                Grand Total: {format_rupees(summary['grand_total_paise'])}
            </div>
            """,
            unsafe_allow_html=True
        )

    # 4. Payment Mode
    payment_mode = st.radio(
        "Payment Mode",
        options=["cash", "upi", "card", "credit"],
        format_func=lambda x: {
            "cash": "💵 Cash",
            "upi": "📱 UPI / QR",
            "card": "💳 Debit / Credit Card",
            "credit": "📝 Credit (Udhaar)"
        }[x],
        horizontal=True
    )

    if payment_mode == "upi":
        shop_cfg = get_shop_settings()
        curr_upi_id = shop_cfg.get("upi_id") or "kirana@upi"
        curr_shop_name = shop_cfg.get("shop_name") or "Apna Kirana"
        grand_total_paise = summary["grand_total_paise"]
        grand_total_rupees = grand_total_paise / 100.0

        with st.container(border=True):
            st.markdown(
                """
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: 700; color: #38BDF8; font-size: 0.95rem;">📱 Dynamic UPI Payment QR</span>
                    <span style="font-size: 0.75rem; background: #0F172A; padding: 2px 8px; border-radius: 6px; border: 1px solid #334155; color: #94A3B8;">
                        GPay • PhonePe • Paytm • BHIM
                    </span>
                </div>
                """,
                unsafe_allow_html=True
            )

            if grand_total_paise <= 0:
                st.info("ℹ️ Add items to cart to generate QR code with bill amount.")
            else:
                qr_bytes = generate_upi_qr_bytes(
                    upi_id=curr_upi_id,
                    payee_name=curr_shop_name,
                    amount_rupees=grand_total_rupees,
                    note=f"Bill at {curr_shop_name}"
                )

                qr_c1, qr_c2 = st.columns([1.1, 1.9], gap="small")
                with qr_c1:
                    st.image(qr_bytes, width=150)
                with qr_c2:
                    st.markdown(
                        f"""
                        <div style="font-size: 0.8rem; color: #94A3B8;">Payable Amount</div>
                        <div style="font-size: 1.4rem; font-weight: 800; color: #38BDF8;">{format_rupees(grand_total_paise)}</div>
                        <div style="font-size: 0.8rem; color: #CBD5E1; margin-top: 2px;">Payee: <b>{curr_shop_name}</b></div>
                        <div style="font-size: 0.75rem; color: #94A3B8;">VPA: <code style="color: #38BDF8;">{curr_upi_id}</code></div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
                    if st.button("🔍 Enlarge QR Popup", use_container_width=True, help="Open full-screen popup for customer to scan"):
                        open_upi_qr_modal(grand_total_paise, qr_bytes, curr_shop_name, curr_upi_id)

    if payment_mode == "credit" and not current_customer_id:
        st.warning("⚠️ Please select a customer to record Credit (Udhaar).")

    # 5. Complete Sale Button
    checkout_disabled = len(st.session_state.cart) == 0 or (payment_mode == "credit" and not current_customer_id)

    if st.button("🚀 Complete Sale & Save Bill", type="primary", use_container_width=True, disabled=checkout_disabled):
        try:
            bill_result = checkout_bill(
                customer_id=current_customer_id,
                payment_mode=payment_mode,
                cart_items=st.session_state.cart,
                discount_type=st.session_state.discount_type,
                discount_val=st.session_state.discount_val,
                created_by=st.session_state.get("user", {}).get("id", 1)
            )

            # Store completed bill in session state for instant reprint / view
            st.session_state.last_completed_bill = bill_result
            # Clear cart and discounts
            st.session_state.cart = []
            st.session_state.discount_val = 0.0
            st.toast(f"🎉 Bill {bill_result['bill_no']} created successfully!", icon="✅")
            st.rerun()

        except Exception as e:
            st.error(f"Checkout Failed: {str(e)}")

    # 6. Post-Checkout Action Card
    if st.session_state.last_completed_bill:
        last_b = st.session_state.last_completed_bill
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.success(f"✅ Last Bill Generated: **{last_b['bill_no']}**")
            st.write(f"Amount Paid: **{format_rupees(last_b['summary']['grand_total_paise'])}**")

            try:
                # Generate PDF bytes for instant download
                pdf_80mm = generate_bill_pdf(last_b["bill_no"], paper_size_override="80mm")
                pdf_a4 = generate_bill_pdf(last_b["bill_no"], paper_size_override="A4")

                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    st.download_button(
                        label="🖨️ Download 80mm Receipt",
                        data=pdf_80mm,
                        file_name=f"{last_b['bill_no']}_thermal.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )
                with b_col2:
                    st.download_button(
                        label="📄 Download A4 Invoice",
                        data=pdf_a4,
                        file_name=f"{last_b['bill_no']}_A4.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Error generating PDF: {str(e)}")

            if st.button("🆕 Start New Sale", key="btn_new_bill", use_container_width=True):
                st.session_state.last_completed_bill = None
                st.rerun()
