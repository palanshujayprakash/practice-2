"""
POS Software - Main Entrypoint, Authentication Gate & Executive Dashboard
Offline Billing & POS for Small Retailers in India.
"""
import streamlit as st
from db.schema import init_db
from db.connection import get_connection
from services.auth_service import authenticate_user
from services.settings_service import get_shop_settings
from services.backup_service import auto_daily_backup
from utils.currency import format_rupees
from utils.ui_components import (
    apply_custom_css,
    init_session_state,
    render_page_header,
    render_metric_card
)

# 1. Page Configuration
st.set_page_config(
    page_title="Retail POS - Dashboard",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inject Desktop POS CSS
apply_custom_css()

# 3. Auto-initialize Database on Startup
init_db()
init_session_state()

# 4. Authentication Gate
if "authenticated" not in st.session_state:
    st.session_state.authenticated = True  # Default logged-in as admin for seamless development; login box below permits switching roles

# Trigger auto daily backup
try:
    auto_daily_backup()
except Exception:
    pass

# Login Modal / Screen if unauthenticated
if not st.session_state.get("authenticated", False):
    _, col_login, _ = st.columns([1, 1.2, 1])
    with col_login:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center;'>🏪 Retail POS Login</h2>", unsafe_allow_html=True)
            st.caption("Secure offline sign-in for Store Owner and Cashier")
            st.markdown("---")

            with st.form("login_form"):
                login_user = st.text_input("Username", value="admin")
                login_pass = st.text_input("Password", type="password", value="admin123")
                login_submit = st.form_submit_button("Sign In 🚀", type="primary", use_container_width=True)

                if login_submit:
                    user_data = authenticate_user(login_user, login_pass)
                    if user_data:
                        st.session_state.authenticated = True
                        st.session_state.user = user_data
                        st.toast(f"✅ Welcome back, {user_data['username']}! ({user_data['role'].title()})", icon="👋")
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

            st.caption("Default Logins:\n• Owner: `admin` / `admin123`\n• Cashier: `cashier` / `cashier123`")
    st.stop()

# 5. Fetch Live Settings and Summary Metrics
settings = get_shop_settings()
current_user = st.session_state.get("user", {"username": "admin", "role": "owner"})

conn = get_connection()
try:
    cur = conn.cursor()
    # Today's sales
    cur.execute(
        """
        SELECT COALESCE(SUM(grand_total_paise), 0) as today_sales, COUNT(id) as today_bills
        FROM bills
        WHERE date(bill_date) = date('now', 'localtime') AND status = 'completed'
        """
    )
    today_stats = cur.fetchone()
    today_sales_paise = today_stats["today_sales"]
    today_bills_count = today_stats["today_bills"]

    # Low stock count
    cur.execute(
        """
        SELECT COUNT(id) as low_count
        FROM products
        WHERE is_active = 1 AND stock_qty <= min_stock_qty
        """
    )
    low_stock_count = cur.fetchone()["low_count"]

    # Total customers and pending credit
    cur.execute(
        """
        SELECT COUNT(id) as cust_count, COALESCE(SUM(credit_balance_paise), 0) as total_udhaar
        FROM customers
        """
    )
    cust_stats = cur.fetchone()
    total_customers = cust_stats["cust_count"]
    total_udhaar_paise = cust_stats["total_udhaar"]

    # Total products in catalog
    cur.execute("SELECT COUNT(id) as prod_count FROM products WHERE is_active = 1")
    total_products = cur.fetchone()["prod_count"]

finally:
    conn.close()

# 6. Top Header Banner
col_h1, col_h2 = st.columns([2.5, 1])
with col_h1:
    render_page_header(
        title=settings.get("shop_name", "Retail POS"),
        subtitle=f"{settings.get('address', '')} | 📞 {settings.get('phone', '')} | GSTIN: {settings.get('gstin', 'Not Registered')}",
        icon="🏪"
    )
with col_h2:
    st.write("")
    role_icon = "👑" if current_user.get("role") == "owner" else "👤"
    st.markdown(
        f"""
        <div style="text-align: right; color: #94A3B8; font-size: 0.95rem;">
            {role_icon} Logged in as: <strong style="color: #38BDF8;">{current_user.get('username', 'Admin')}</strong>
            <span class="badge-success" style="margin-left: 6px;">{current_user.get('role', 'Owner').upper()}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

# 7. Metric Cards Row
c1, c2, c3, c4 = st.columns(4)

with c1:
    render_metric_card(
        title="Today's Total Sales",
        value=format_rupees(today_sales_paise),
        subtext=f"{today_bills_count} bills generated today"
    )

with c2:
    render_metric_card(
        title="Active Catalog",
        value=f"{total_products:,} Items",
        subtext="Available for barcode scanning"
    )

with c3:
    badge = "⚠️ Restock Needed" if low_stock_count > 0 else "✅ Healthy Inventory"
    render_metric_card(
        title="Low Stock Alerts",
        value=f"{low_stock_count} Items",
        subtext=badge
    )

with c4:
    render_metric_card(
        title="Pending Udhaar (Credit)",
        value=format_rupees(total_udhaar_paise),
        subtext=f"Across {total_customers} registered customers"
    )

st.markdown("<br>", unsafe_allow_html=True)

# 8. Quick Navigation Action Blocks
st.subheader("⚡ Quick POS Actions")
qa1, qa2, qa3, qa4 = st.columns(4)

with qa1:
    with st.container(border=True):
        st.markdown("#### ⚡ New Sale")
        st.caption("Open high-speed barcode checkout terminal")
        if st.button("Open Billing 🚀", use_container_width=True, type="primary"):
            st.switch_page("pages/1_⚡_Billing.py")

with qa2:
    with st.container(border=True):
        st.markdown("#### 📦 Inventory")
        st.caption("Add items, modify prices, or bulk import")
        if st.button("Manage Products", use_container_width=True):
            st.switch_page("pages/2_📦_Products.py")

with qa3:
    with st.container(border=True):
        st.markdown("#### 📜 Bill History")
        st.caption("Look up past bills, reprint, or audit")
        if st.button("View Bill History", use_container_width=True):
            st.switch_page("pages/4_📜_Bill_History.py")

with qa4:
    with st.container(border=True):
        st.markdown("#### ⚙️ Settings")
        st.caption("Store profile, users, and DB backups")
        if st.button("Store Settings", use_container_width=True):
            st.switch_page("pages/6_⚙️_Settings.py")

st.markdown("---")

# 9. Sidebar User & Store Info
with st.sidebar:
    if settings.get("logo_blob"):
        st.image(settings["logo_blob"], width=130)
    st.markdown(f"**{settings.get('shop_name', 'Store')}**")
    st.caption(f"Invoice Mode: {settings.get('paper_size', '80mm')} Thermal")
    st.markdown("---")
    st.markdown(f"**Current User:** {current_user.get('username')} ({current_user.get('role').title()})")

    # Switch user or logout
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        # Quick switch to cashier role for testing
        target_role = "cashier" if current_user.get("role") == "owner" else "owner"
        btn_label = "Switch Cashier" if target_role == "cashier" else "Switch Owner"
        if st.button(btn_label, use_container_width=True):
            st.session_state.user = {
                "id": 2 if target_role == "cashier" else 1,
                "username": target_role,
                "role": target_role
            }
            st.toast(f"Switched role to {target_role.upper()}", icon="🔄")
            st.rerun()

    with col_u2:
        if st.button("Logout 🚪", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()

    st.markdown("---")
    st.caption("💡 Tip: Cashiers have restricted access (cannot edit prices, cancel bills, or alter shop settings).")
