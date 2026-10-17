"""
Store Settings, User Management & Database Backups Page (Phase 6)
Role-protected configuration: shop profile, GSTIN, cashier accounts, and one-click DB backup/restore.
"""
from pathlib import Path
import streamlit as st
import pandas as pd
from db.schema import init_db
from services.settings_service import get_shop_settings, update_shop_settings
from services.auth_service import get_all_users, create_user, change_user_password
from services.backup_service import (
    create_backup,
    list_backups,
    restore_backup,
    validate_backup_file,
)
from utils.ui_components import apply_custom_css, init_session_state, render_page_header

st.set_page_config(page_title="Settings & Backups - POS", page_icon="⚙️", layout="wide")
apply_custom_css()
init_session_state()
init_db()

render_page_header(
    title="Store Settings, Users & Backups",
    subtitle="Configure store profile, cashier user permissions, and database backup & restore",
    icon="⚙️"
)

current_user = st.session_state.get("user", {"role": "owner"})
is_owner = current_user.get("role") == "owner"

if not is_owner:
    st.warning("⚠️ Restricted View: You are signed in as a Cashier. Store settings, user management, and database restore are only editable by the Store Owner.")

# Settings Tabs
tab_profile, tab_users, tab_backup = st.tabs([
    "🏪 Store Profile & Receipt Format",
    "👥 User Accounts & Roles",
    "💾 Database Backup & Restore",
])

# -------------------------------------------------------------
# TAB 1: STORE PROFILE & RECEIPT FORMAT
# -------------------------------------------------------------
with tab_profile:
    settings = get_shop_settings()
    col_form, col_preview = st.columns([1.6, 1], gap="large")

    with col_form:
        st.subheader("Edit Shop Details")
        with st.form("settings_form", clear_on_submit=False):
            shop_name = st.text_input("Shop Name *", value=settings.get("shop_name", ""), disabled=not is_owner)
            address = st.text_area("Store Address", value=settings.get("address", ""), height=80, disabled=not is_owner)

            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                phone = st.text_input("Contact Phone", value=settings.get("phone", ""), disabled=not is_owner)
            with col_p2:
                gstin = st.text_input("GSTIN Number (Optional)", value=settings.get("gstin", ""), disabled=not is_owner)
            with col_p3:
                upi_id = st.text_input("Merchant UPI ID / VPA", value=settings.get("upi_id", "kirana@upi"), help="e.g. 9876543210@okaxis or store@upi", disabled=not is_owner)

            bill_footer = st.text_input("Bill Footer Note", value=settings.get("bill_footer", "Thank you! Visit again."), disabled=not is_owner)

            col_sz1, col_sz2 = st.columns(2)
            with col_sz1:
                current_sz = settings.get("paper_size", "80mm")
                paper_size = st.selectbox(
                    "Default Invoice Format",
                    options=["80mm", "A4"],
                    index=0 if current_sz == "80mm" else 1,
                    disabled=not is_owner
                )

            with col_sz2:
                logo_file = st.file_uploader("Upload Store Logo", type=["png", "jpg", "jpeg"], disabled=not is_owner)

            remove_logo = False
            if settings.get("logo_blob") and is_owner:
                remove_logo = st.checkbox("Remove current logo", value=False)

            submitted = st.form_submit_button("💾 Save Settings", use_container_width=True, type="primary", disabled=not is_owner)

            if submitted and is_owner:
                if not shop_name.strip():
                    st.error("Shop Name is mandatory.")
                else:
                    logo_blob = None
                    keep_logo = True
                    if remove_logo:
                        keep_logo = False
                    elif logo_file is not None:
                        logo_blob = logo_file.read()

                    try:
                        update_shop_settings(
                            shop_name=shop_name,
                            address=address,
                            phone=phone,
                            gstin=gstin,
                            bill_footer=bill_footer,
                            paper_size=paper_size,
                            logo_blob=logo_blob,
                            keep_existing_logo=keep_logo,
                            upi_id=upi_id
                        )
                        st.toast("✅ Settings saved successfully!", icon="🎉")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving settings: {str(e)}")

    with col_preview:
        st.subheader("Invoice Header Preview")
        with st.container(border=True):
            if settings.get("logo_blob"):
                st.image(settings["logo_blob"], width=130)
            else:
                st.info("No logo uploaded. Standard text header will be printed.")

            st.markdown(f"### {settings.get('shop_name', 'Store Name')}")
            if settings.get("address"):
                st.write(f"📍 {settings.get('address')}")
            if settings.get("phone"):
                st.write(f"📞 {settings.get('phone')}")
            if settings.get("gstin"):
                st.write(f"🏷️ **GSTIN:** `{settings.get('gstin')}`")

            st.markdown("---")
            st.caption(f"**Receipt Paper:** {settings.get('paper_size', '80mm')}")
            st.caption(f"**Footer Note:** *{settings.get('bill_footer', '')}*")

# -------------------------------------------------------------
# TAB 2: USER ACCOUNTS & ROLES
# -------------------------------------------------------------
with tab_users:
    st.subheader("User Accounts & Role Permissions")
    st.caption("Role Permissions: Owner (Full control) | Cashier (Billing only, cannot change prices or cancel bills)")

    col_u_list, col_u_add = st.columns([1.5, 1], gap="large")

    with col_u_list:
        users = get_all_users()
        user_rows = []
        for u in users:
            user_rows.append({
                "User ID": u["id"],
                "Username": u["username"],
                "Role": u["role"].upper(),
                "Created At": str(u["created_at"])[:16],
            })
        st.dataframe(pd.DataFrame(user_rows), use_container_width=True, hide_index=True)

        if is_owner:
            st.markdown("##### Change User Password")
            with st.form("pwd_form", clear_on_submit=True):
                target_user = st.selectbox("Select User", options=[u["username"] for u in users])
                new_pwd = st.text_input("New Password", type="password")
                pwd_submit = st.form_submit_button("Update Password", use_container_width=True)

                if pwd_submit:
                    u_obj = next((u for u in users if u["username"] == target_user), None)
                    if u_obj and new_pwd:
                        try:
                            change_user_password(u_obj["id"], new_pwd)
                            st.toast(f"✅ Password for '{target_user}' updated!", icon="🔑")
                        except Exception as e:
                            st.error(str(e))

    with col_u_add:
        if is_owner:
            st.subheader("Create New User")
            with st.form("add_user_form", clear_on_submit=True):
                nu_name = st.text_input("Username *", placeholder="e.g. cashier2")
                nu_pass = st.text_input("Password *", type="password")
                nu_role = st.selectbox("Role", options=["cashier", "owner"])
                nu_submit = st.form_submit_button("➕ Create Account", type="primary", use_container_width=True)

                if nu_submit:
                    if not nu_name.strip() or not nu_pass.strip():
                        st.error("Username and Password are required.")
                    else:
                        try:
                            create_user(nu_name, nu_pass, nu_role)
                            st.toast(f"✅ User '{nu_name}' ({nu_role}) created!", icon="👤")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to create user: {str(e)}")
        else:
            st.info("Creating new accounts requires Store Owner privileges.")

# -------------------------------------------------------------
# TAB 3: DATABASE BACKUP & RESTORE
# -------------------------------------------------------------
with tab_backup:
    st.subheader("Database Backup & Disaster Recovery")
    st.write("Keep your billing data safe. Backups are stored locally in the `data/backups/` directory.")

    col_b_act, col_b_rest = st.columns([1, 1], gap="large")

    with col_b_act:
        with st.container(border=True):
            st.markdown("#### 💾 Create Database Backup")
            st.write("Generates an instant online snapshot of all tables, products, and invoices.")
            backup_note = st.text_input("Backup Note (Optional)", placeholder="e.g. before_eod, pre_audit")
            if st.button("🚀 Backup Now", type="primary", use_container_width=True):
                try:
                    fpath = create_backup(notes=backup_note or "manual")
                    st.toast(f"✅ Backup created: {Path(fpath).name}", icon="💾")
                    st.rerun()
                except Exception as e:
                    st.error(f"Backup failed: {str(e)}")

    with col_b_rest:
        with st.container(border=True):
            st.markdown("#### 🔄 Restore from Backup File")
            if not is_owner:
                st.warning("Only Store Owners can restore backups.")
            else:
                st.write("Select a previous `.db` file to restore the entire database.")
                restore_file = st.file_uploader("Upload Backup Database (.db)", type=["db"])

                if restore_file is not None:
                    # Save temporary file for validation
                    temp_restore_path = Path("data") / "temp_restore.db"
                    with open(temp_restore_path, "wb") as f:
                        f.write(restore_file.read())

                    if not validate_backup_file(str(temp_restore_path)):
                        st.error("Uploaded file is not a valid POS database backup.")
                    else:
                        st.success("✅ Valid backup file confirmed!")
                        if st.button("⚠️ Confirm Database Restore", type="primary", use_container_width=True):
                            try:
                                restore_backup(str(temp_restore_path))
                                if temp_restore_path.exists():
                                    temp_restore_path.unlink()
                                st.toast("🎉 Database restored successfully!", icon="🔄")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Restore failed: {str(e)}")

    st.markdown("---")
    st.subheader("📁 Available Local Backups")
    backups = list_backups()
    if not backups:
        st.info("No backups found in `data/backups/`. Click 'Backup Now' above to generate one.")
    else:
        for b in backups[:10]:
            with st.container(border=True):
                cb1, cb2, cb3 = st.columns([2.5, 1, 1])
                with cb1:
                    st.markdown(f"**{b['filename']}**")
                    st.caption(f"Created: {b['created_at']}")
                with cb2:
                    st.write(f"Size: `{b['size_kb']} KB`")
                with cb3:
                    with open(b["filepath"], "rb") as f:
                        st.download_button(
                            label="📥 Download",
                            data=f.read(),
                            file_name=b["filename"],
                            mime="application/x-sqlite3",
                            key=f"dl_bkp_{b['filename']}",
                            use_container_width=True
                        )
