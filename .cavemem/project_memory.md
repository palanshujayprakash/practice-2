# Cavemem: POS Desktop Software Project Memory

## Project Overview
Offline Billing / POS App for Indian retail (Kirana, Medical, Mobile, Garments).
Tech stack: Streamlit, SQLite (sqlite3), ReportLab, openpyxl, pandas, Plotly, pywebview, PyInstaller.

## Core Architectural Decisions
- Currency math: All prices/amounts stored as **integer paise** (`10050` = `₹100.50`). Never float.
- Database: SQLite thread-safe with `PRAGMA foreign_keys = ON;`, WAL mode, and `isolation_level="IMMEDIATE"`.
- DB Location: `data/pos.db` (auto-created on first run).
- Bill snapshots: `bill_items` stores historical snapshot of product name, price, GST rate at time of checkout.
- Sequential Bill numbering: `INV-YYYY-XXXX` with exponential backoff retry loop on concurrent checkouts.

## Active Skills & Rules
- Superpowers (Planning, TDD, Systematic Debugging, Code Review, Verification)
- Ponytail (lean, minimal code, zero overengineering)
- Caveman (concise conversational replies, complete code/docs)
- UI Guidelines (custom professional CSS, dark/light theme, metric cards, 1366x768 responsive)

## Stress & Crash Testing Results
- **Attacks & Chaos Scenarios Executed**:
  1. Extreme Monetary Values: 1 paisa (₹0.01) up to ₹10,00,00,000 (10 crore). Handled cleanly.
  2. Discount Fuzzing: Negative discounts, 100% discount, 200% discount, discount > bill total. All clamped safely, grand total never drops below zero.
  3. SQL Injection Attempts: Parameterized queries prevented injection across searches, barcodes, customer names, and audit filters.
  4. Multi-language Unicode & Emojis: Tested Hindi (`टाटा नमक १ किलो 🧂`), Tamil, and symbols. Handled without crashing.
  5. Long Receipt Stress: Generated 60-item 80mm thermal receipts without ReportLab canvas overflow.
  6. Corrupt File Uploads: Non-SQLite files and corrupt Excel sheets rejected with friendly error messages.
  7. High Concurrency Race Conditions: 20 simultaneous checkout threads tested under WAL mode with zero collisions.

- **Bugs Caught & Hardened**:
  - Fixed Windows file lock leak in `validate_backup_file` by adding a guaranteed `finally` connection cleanup block.
  - Hardened concurrent bill creation against sequence collisions using `isolation_level="IMMEDIATE"` and a 10-attempt retry backoff loop in `checkout_bill`.

- **Test Suite Status**: 37/37 tests passing (6.75s).

## Kirana Store Dataset (Seeded in data/pos.db)
- **Products**: 69 authentic items across 13 retail categories (Atta, Rice, Dals, Spices, Dairy, Snacks, Biscuits, Chocolates, Cleaning, Personal Care, Edible Oils, Sugar, Tea & Beverages) with realistic barcodes (EAN-13), standard Indian GST rates (0%, 5%, 12%, 18%), purchase/selling prices, and initial stock.
- **Customers**: 10 neighborhood customer profiles with realistic phone numbers, addresses, and credit (khata/udhaar) balances.
- **Transactions**: 106 backdated retail invoices spread across 25 days with varied payment methods (Cash, UPI, Card, Credit) for instant analytics, sales charts, and reporting.

## Dynamic UPI QR Code Integration
- **NPCI Specification**: `upi://pay?pa={upi_id}&pn={merchant_name}&am={amount_rupees}&cu=INR&tn={note}` generated dynamically in [`services/upi_service.py`](file:///c:/Users/palan/OneDrive/Desktop/software/services/upi_service.py).
- **Billing Checkout Integration**: Selecting "📱 UPI / QR" in [`pages/1_⚡_Billing.py`](file:///c:/Users/palan/OneDrive/Desktop/software/pages/1_⚡_Billing.py) automatically generates and renders the exact bill amount QR code inline with payee name, UPI VPA, and GPay/PhonePe/Paytm badges.
- **Fullscreen Counter Modal**: "🔍 Enlarge QR Popup" button triggers `@st.dialog("📱 Scan & Pay via UPI")` for counter-facing display.
- **Store Configuration**: Merchant UPI VPA editable in [`pages/6_⚙️_Settings.py`](file:///c:/Users/palan/OneDrive/Desktop/software/pages/6_⚙️_Settings.py) with database persistence (`shop_settings.upi_id`).
