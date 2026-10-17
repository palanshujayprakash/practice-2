"""
Products & Inventory Management Page (Phase 2)
Supports st.data_editor inline editing, low-stock highlighting, product creation, and bulk CSV/Excel import.
"""
import io
import pandas as pd
import streamlit as st
from db.schema import init_db
from services.product_service import (
    get_all_products,
    get_all_categories,
    get_low_stock_products,
    add_product,
    update_product,
    delete_product,
    import_products_from_dataframe,
)
from utils.currency import format_rupees, paise_to_rupees_decimal, rupees_to_paise
from utils.ui_components import (
    apply_custom_css,
    init_session_state,
    render_page_header,
    render_metric_card,
)

st.set_page_config(page_title="Products & Inventory - POS", page_icon="📦", layout="wide")
apply_custom_css()
init_session_state()
init_db()

render_page_header(
    title="Products & Inventory Catalog",
    subtitle="Manage retail items, live stock levels, barcodes, and bulk imports",
    icon="📦"
)

# 1. Fetch current catalog metrics
all_products = get_all_products(active_only=True)
low_stock_items = get_low_stock_products()
categories = get_all_categories()

total_count = len(all_products)
low_count = len(low_stock_items)
total_inventory_val_paise = sum(
    p["selling_price_paise"] * p["stock_qty"] for p in all_products
)

# 2. Metric Cards Row
m1, m2, m3 = st.columns(3)
with m1:
    render_metric_card("Total Products", f"{total_count:,} Items", "Active catalog items")
with m2:
    badge = "⚠️ Urgent Restock" if low_count > 0 else "✅ Sufficient Stock"
    render_metric_card("Low Stock Alerts", f"{low_count} Items", badge)
with m3:
    render_metric_card("Inventory Asset Value", format_rupees(int(total_inventory_val_paise)), "Based on selling price")

st.markdown("<br>", unsafe_allow_html=True)

# 3. Main Navigation Tabs
tab_view, tab_add, tab_bulk, tab_low = st.tabs([
    "📋 Inventory Table & Inline Edit",
    "➕ Add New Product",
    "📥 Bulk Import (Excel / CSV)",
    "⚠️ Low Stock Alerts",
])

# -------------------------------------------------------------
# TAB 1: INVENTORY TABLE & INLINE EDIT (st.data_editor)
# -------------------------------------------------------------
with tab_view:
    # Filter Row
    f1, f2, f3 = st.columns([1.5, 1, 1])
    with f1:
        search_query = st.text_input("🔍 Search Name or Barcode", placeholder="Type item name or scan barcode...", key="prod_search")
    with f2:
        selected_cat = st.selectbox("Filter Category", options=["All"] + categories, key="prod_cat_filter")
    with f3:
        only_low = st.checkbox("Show Only Low Stock", value=False, key="prod_low_filter")

    # Filtered products
    filtered = get_all_products(
        search_term=search_query,
        category=selected_cat,
        active_only=True
    )
    if only_low:
        filtered = [p for p in filtered if p["stock_qty"] <= p["min_stock_qty"]]

    if not filtered:
        st.info("No products match the selected filters.")
    else:
        # Prepare DataFrame for st.data_editor
        table_data = []
        for p in filtered:
            table_data.append({
                "ID": p["id"],
                "Barcode": p["barcode"] or "",
                "Name": p["name"],
                "Category": p["category"],
                "Unit": p["unit"],
                "Cost Price (₹)": float(paise_to_rupees_decimal(p["purchase_price_paise"])),
                "Selling Price (₹)": float(paise_to_rupees_decimal(p["selling_price_paise"])),
                "GST Rate (%)": float(p["gst_rate"]),
                "Stock Qty": float(p["stock_qty"]),
                "Min Alert Qty": float(p["min_stock_qty"]),
                "Low Stock": "⚠️ LOW" if p["stock_qty"] <= p["min_stock_qty"] else "✅ OK",
            })

        df = pd.DataFrame(table_data)

        # Apply red highlighting to low-stock rows
        def highlight_low_stock(row):
            if row["Stock Qty"] <= row["Min Alert Qty"]:
                return ["background-color: rgba(239, 68, 68, 0.2); color: #FCA5A5;"] * len(row)
            return [""] * len(row)

        is_owner = st.session_state.get("user", {}).get("role") == "owner"
        disabled_cols = ["ID", "Low Stock"] if is_owner else ["ID", "Low Stock", "Cost Price (₹)", "Selling Price (₹)"]

        if not is_owner:
            st.info("ℹ️ Cashier Mode: Price editing is disabled. Contact Store Owner to change selling or cost prices.")
        else:
            st.caption("💡 Tip: Double-click any cell to edit details inline, then click **'Save Table Edits'** below.")

        # Editable Data Editor
        edited_df = st.data_editor(
            df,
            key="products_data_editor",
            use_container_width=True,
            num_rows="dynamic" if is_owner else "fixed",
            disabled=disabled_cols,
            column_config={
                "ID": st.column_config.NumberColumn("ID", disabled=True, width=60),
                "Barcode": st.column_config.TextColumn("Barcode", width=120),
                "Name": st.column_config.TextColumn("Product Name", required=True, width=220),
                "Category": st.column_config.TextColumn("Category", width=120),
                "Unit": st.column_config.SelectboxColumn("Unit", options=["pcs", "kg", "gms", "ltr", "box", "meter"], required=True, width=80),
                "Cost Price (₹)": st.column_config.NumberColumn("Cost (₹)", min_value=0.0, step=0.5, format="₹%.2f", disabled=not is_owner),
                "Selling Price (₹)": st.column_config.NumberColumn("Selling Price (₹)", min_value=0.0, step=0.5, format="₹%.2f", required=True, disabled=not is_owner),
                "GST Rate (%)": st.column_config.SelectboxColumn("GST (%)", options=[0.0, 5.0, 12.0, 18.0, 28.0], required=True),
                "Stock Qty": st.column_config.NumberColumn("Stock", min_value=0.0, step=1.0),
                "Min Alert Qty": st.column_config.NumberColumn("Min Alert", min_value=0.0, step=1.0),
                "Low Stock": st.column_config.TextColumn("Status", disabled=True, width=100),
            },
            hide_index=True
        )

        col_save, col_del = st.columns([1, 4])
        with col_save:
            if st.button("💾 Save Table Edits", type="primary", use_container_width=True):
                changes = st.session_state.get("products_data_editor", {})
                edited_rows = changes.get("edited_rows", {})
                added_rows = changes.get("added_rows", [])
                deleted_rows = changes.get("deleted_rows", [])

                errors = []
                success_count = 0

                # 1. Process Edits
                for row_idx, edits in edited_rows.items():
                    orig = df.iloc[row_idx]
                    p_id = int(orig["ID"])
                    name = edits.get("Name", orig["Name"])
                    barcode = edits.get("Barcode", orig["Barcode"])
                    category = edits.get("Category", orig["Category"])
                    unit = edits.get("Unit", orig["Unit"])
                    cost_rs = edits.get("Cost Price (₹)", orig["Cost Price (₹)"])
                    sell_rs = edits.get("Selling Price (₹)", orig["Selling Price (₹)"])
                    gst = edits.get("GST Rate (%)", orig["GST Rate (%)"])
                    stock = edits.get("Stock Qty", orig["Stock Qty"])
                    min_stock = edits.get("Min Alert Qty", orig["Min Alert Qty"])

                    try:
                        update_product(
                            product_id=p_id,
                            name=str(name),
                            selling_price_paise=rupees_to_paise(sell_rs),
                            purchase_price_paise=rupees_to_paise(cost_rs),
                            barcode=str(barcode) if barcode else None,
                            category=str(category),
                            unit=str(unit),
                            gst_rate=float(gst),
                            stock_qty=float(stock),
                            min_stock_qty=float(min_stock)
                        )
                        success_count += 1
                    except Exception as e:
                        errors.append(f"Product #{p_id}: {str(e)}")

                # 2. Process Deletions
                for row_idx in deleted_rows:
                    p_id = int(df.iloc[row_idx]["ID"])
                    try:
                        delete_product(p_id, soft_delete=True)
                        success_count += 1
                    except Exception as e:
                        errors.append(f"Delete Product #{p_id}: {str(e)}")

                # 3. Process Additions
                for new_row in added_rows:
                    name = new_row.get("Name")
                    if not name:
                        errors.append("Added row missing Product Name.")
                        continue
                    sell_rs = new_row.get("Selling Price (₹)", 0.0)
                    cost_rs = new_row.get("Cost Price (₹)", 0.0)
                    barcode = new_row.get("Barcode")
                    category = new_row.get("Category", "General")
                    unit = new_row.get("Unit", "pcs")
                    gst = new_row.get("GST Rate (%)", 0.0)
                    stock = new_row.get("Stock Qty", 0.0)
                    min_stock = new_row.get("Min Alert Qty", 5.0)

                    try:
                        add_product(
                            name=str(name),
                            selling_price_paise=rupees_to_paise(sell_rs),
                            purchase_price_paise=rupees_to_paise(cost_rs),
                            barcode=str(barcode) if barcode else None,
                            category=str(category),
                            unit=str(unit),
                            gst_rate=float(gst),
                            stock_qty=float(stock),
                            min_stock_qty=float(min_stock)
                        )
                        success_count += 1
                    except Exception as e:
                        errors.append(f"Add Product: {str(e)}")

                if errors:
                    st.error("Some updates failed:\n" + "\n".join(errors))
                if success_count > 0:
                    st.toast(f"✅ Successfully updated {success_count} record(s)!", icon="🎉")
                    st.rerun()

# -------------------------------------------------------------
# TAB 2: ADD NEW PRODUCT (st.form)
# -------------------------------------------------------------
with tab_add:
    st.subheader("Add Single Product to Catalog")
    with st.form("add_product_form", clear_on_submit=True):
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            new_name = st.text_input("Product Name *", placeholder="e.g. Tata Salt 1kg, Parle-G 250g")
            new_barcode = st.text_input("Barcode / SKU (Optional)", placeholder="Scan with barcode scanner or enter code")
            new_category = st.text_input("Category", value="General", placeholder="Grocery, Snacks, Personal Care, etc.")
            new_unit = st.selectbox("Unit of Measure", options=["pcs", "kg", "gms", "ltr", "box", "meter"], index=0)

        with col_a2:
            new_sp = st.number_input("Selling Price (₹) *", min_value=0.0, value=0.0, step=1.0, format="%.2f")
            new_pp = st.number_input("Cost / Purchase Price (₹)", min_value=0.0, value=0.0, step=1.0, format="%.2f")
            new_gst = st.selectbox("GST Tax Slab (%)", options=[0.0, 5.0, 12.0, 18.0, 28.0], index=0)

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                new_stock = st.number_input("Opening Stock Qty", min_value=0.0, value=10.0, step=1.0)
            with col_s2:
                new_min_stock = st.number_input("Min Alert Qty", min_value=0.0, value=5.0, step=1.0)

        submitted_add = st.form_submit_button("➕ Add Product to Inventory", use_container_width=True, type="primary")

        if submitted_add:
            if not is_owner:
                st.error("🚫 Access Denied: Only Store Owner can add new products.")
            elif not new_name.strip():
                st.error("Product Name is mandatory.")
            elif new_sp < 0:
                st.error("Selling price cannot be negative.")
            else:
                try:
                    p_id = add_product(
                        name=new_name,
                        selling_price_paise=rupees_to_paise(new_sp),
                        purchase_price_paise=rupees_to_paise(new_pp),
                        barcode=new_barcode if new_barcode else None,
                        category=new_category,
                        unit=new_unit,
                        gst_rate=new_gst,
                        stock_qty=new_stock,
                        min_stock_qty=new_min_stock
                    )
                    st.toast(f"✅ Product '{new_name}' added successfully! (ID: {p_id})", icon="📦")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add product: {str(e)}")

# -------------------------------------------------------------
# TAB 3: BULK IMPORT (CSV / EXCEL)
# -------------------------------------------------------------
with tab_bulk:
    st.subheader("Bulk Import Products from CSV or Excel")
    st.write("Upload your inventory spreadsheet to import hundreds of items in one click.")

    # Sample template download
    sample_df = pd.DataFrame([
        {
            "Barcode": "8901030383792",
            "Name": "Fortune Sunflower Oil 1L",
            "Category": "Grocery",
            "Unit": "ltr",
            "Selling Price": 145.00,
            "Purchase Price": 130.00,
            "GST Rate": 5.0,
            "Stock Qty": 50,
            "Min Stock Qty": 10
        },
        {
            "Barcode": "8901725181222",
            "Name": "Aashirvaad Shudh Chakki Atta 5kg",
            "Category": "Grocery",
            "Unit": "pcs",
            "Selling Price": 260.00,
            "Purchase Price": 235.00,
            "GST Rate": 0.0,
            "Stock Qty": 25,
            "Min Stock Qty": 5
        },
        {
            "Barcode": "8901058852331",
            "Name": "Maggi 2-Minute Masala Noodles 70g",
            "Category": "Snacks",
            "Unit": "pcs",
            "Selling Price": 14.00,
            "Purchase Price": 12.00,
            "GST Rate": 12.0,
            "Stock Qty": 100,
            "Min Stock Qty": 20
        }
    ])

    # Convert to CSV and Excel bytes for sample download
    csv_bytes = sample_df.to_csv(index=False).encode("utf-8")
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        sample_df.to_excel(writer, index=False, sheet_name="Products")
    excel_bytes = excel_buffer.getvalue()

    col_t1, col_t2 = st.columns([1, 1])
    with col_t1:
        st.download_button(
            "📥 Download Sample Excel Template (.xlsx)",
            data=excel_bytes,
            file_name="pos_products_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with col_t2:
        st.download_button(
            "📥 Download Sample CSV Template (.csv)",
            data=csv_bytes,
            file_name="pos_products_template.csv",
            mime="text/csv",
            use_container_width=True
        )

    st.markdown("---")

    uploaded_file = st.file_uploader(
        "Choose an Excel (.xlsx, .xls) or CSV file",
        type=["csv", "xlsx", "xls"],
        help="Make sure the file contains 'Name' and 'Selling Price' columns."
    )

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)

            st.write(f"**Preview of Uploaded Data ({len(df_upload)} rows):**")
            st.dataframe(df_upload.head(10), use_container_width=True)

            if st.button("🚀 Confirm & Import All Rows", type="primary", use_container_width=True):
                if not is_owner:
                    st.error("🚫 Access Denied: Only Store Owner can bulk import products.")
                else:
                    with st.spinner("Importing items into catalog..."):
                        result = import_products_from_dataframe(df_upload)
                    if result["success"] > 0:
                        st.success(f"🎉 Successfully imported {result['success']} product(s)!")
                    if result["errors"]:
                        st.warning(f"{len(result['errors'])} error(s) encountered during import:")
                        for err in result["errors"][:10]:
                            st.write(f"- {err}")
                        if len(result["errors"]) > 10:
                            st.write(f"... and {len(result['errors']) - 10} more errors.")
                    if result["success"] > 0:
                        st.rerun()
        except Exception as e:
            st.error(f"Failed to read file: {str(e)}")

# -------------------------------------------------------------
# TAB 4: LOW STOCK ALERTS
# -------------------------------------------------------------
with tab_low:
    st.subheader("Items Below Minimum Stock Threshold")
    if not low_stock_items:
        st.success("✅ Great job! All active items have sufficient stock.")
    else:
        st.warning(f"⚠️ {len(low_stock_items)} item(s) need immediate re-ordering!")
        low_table = []
        for it in low_stock_items:
            shortage = it["min_stock_qty"] - it["stock_qty"]
            low_table.append({
                "Barcode": it["barcode"] or "-",
                "Item Name": it["name"],
                "Category": it["category"],
                "Current Stock": f"{it['stock_qty']} {it['unit']}",
                "Min Alert Qty": f"{it['min_stock_qty']} {it['unit']}",
                "Deficit / Reorder Qty": f"{shortage} {it['unit']}",
                "Unit Price": format_rupees(it["selling_price_paise"]),
            })
        st.dataframe(pd.DataFrame(low_table), use_container_width=True)
