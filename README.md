# Retail POS & Billing Software (Offline Desktop App)

A complete, production-grade, offline Point-of-Sale (POS) and Billing desktop application tailored for small retail stores across India (Kirana, Medical, Mobile, and Garment shops).

Built with **Streamlit**, **SQLite**, **ReportLab**, **openpyxl**, **Plotly**, and **pywebview**, packaged as a native desktop application with zero external internet requirements.

---

## 🌟 Key Features

- **⚡ Fast POS Terminal**:
  - Auto-focused barcode / search box: Scan barcode or type item name and press Enter to instantly increment the cart.
  - Live cart table with editable quantities, line totals, and item removal.
  - Transparent GST tax breakdown (standard retail MRP inclusive calculation).
  - Flexible discounts: Fixed (₹) or Percentage (%).
  - Multiple payment modes: **Cash**, **UPI / QR**, **Card**, and **Credit (Udhaar)**.
  - Stock auto-deduction and sequential invoice numbering (`INV-YYYY-XXXX`).

- **📦 Inventory Management**:
  - Interactive table with `st.data_editor` for rapid inline editing and batch saves.
  - Low-stock alerts highlighted in red with deficit reorder quantities.
  - Strict input validations: Non-negative prices, positive stock quantities, and unique barcodes.
  - One-click Bulk Import from Excel (`.xlsx`) or CSV (`.csv`) with sample template downloads.

- **👥 Customer Directory & Udhaar Ledger**:
  - Tracks customer purchase volume and outstanding credit balances.
  - Interactive payment settlement dialog with instant balance adjustment.
  - Full purchase history inspection per customer.

- **📄 Clean PDF Invoices**:
  - **80mm Thermal Receipt**: Dynamic height roll sizing (prevents paper waste), logo, shop header, GSTIN, itemized table, and footer note.
  - **A4 Full Tax Invoice**: Professional grid format with HSN/GST rate %, CGST/SGST tax liability breakdown, and authorized signatory block.
  - One-click PDF download on checkout and historical reprint engine.

- **📊 Analytics & Tax Reports**:
  - Interactive Plotly visualizations: Daily Sales Velocity (bar chart) and Top Selling Items (donut chart).
  - Comprehensive GST slab summary table (CGST, SGST, and total tax liability).
  - Multi-sheet Excel workbook export (`openpyxl`) featuring:
    1. *Invoices Summary*
    2. *GST Tax Slabs*
    3. *Top Selling Items*
    4. *Low Stock Inventory*

- **🛡️ Safety & Role-Based Access Control (RBAC)**:
  - Salted PBKDF2-HMAC-SHA256 password security with constant-time verification.
  - **Owner Role (`admin` / `admin123`)**: Unrestricted access to settings, user management, price alterations, invoice cancellations, and DB restores.
  - **Cashier Role (`cashier` / `cashier123`)**: Fast checkout only. Price editing, new item creation, bulk import, and invoice cancellations are restricted.
  - Hot online SQLite backup API (`data/backups/`) with automated daily backups on boot and one-click manual restore with pre-restore safety snapshots.

---

## 🚀 Quickstart Guide

### 1. Installation
Clone or navigate to the project directory and install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Running the Application

#### Option A: Native Desktop Window (Recommended for PC)
Runs Streamlit in the background and opens the POS in a clean, standalone desktop window via `pywebview`:
```bash
python launcher.py
```

#### Option B: Browser Mode
```bash
streamlit run app.py
```
Open **http://localhost:8501** in your browser.

---

## 🛠️ Packaging into a Standalone Windows Executable (.exe)

To bundle the entire software into a single standalone `.exe` with icon that runs on clean Windows PCs without Python installed:

```bash
python build.py
```
The output executable will be created at:
```text
dist/RetailPOS.exe
```

---

## 🧪 Automated Test Suite

Run the complete automated test suite covering currency precision, database auto-initialization, inventory validation, atomic billing, PDF generation, invoice cancellation, and disaster recovery:

```bash
pytest tests/ -v
```

---

## 📋 Default Credentials
- **Store Owner:** `admin` / `admin123`
- **Cashier:** `cashier` / `cashier123`
