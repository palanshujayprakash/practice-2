"""
Comprehensive Kirana Store Real-World Data Seeder.
Populates 60+ authentic retail products, Indian EAN barcodes, GST slabs,
neighborhood customers with udhaar balances, and historical sales transactions.
"""
import random
from datetime import datetime, timedelta
import sqlite3
from db.connection import get_connection
from utils.currency import rupees_to_paise
from services.product_service import add_product
from services.customer_service import add_customer
from services.billing_service import checkout_bill

# 1. Authentic Kirana Products
KIRANA_CATALOG = [
    # Grains, Flours & Pulses (0% GST)
    ("Aashirvaad Shudh Chakki Atta 5kg", "8901725181222", "Atta & Flours", "pcs", 235.00, 260.00, 0.0, 35, 8),
    ("Aashirvaad Shudh Chakki Atta 10kg", "8901725181239", "Atta & Flours", "pcs", 440.00, 485.00, 0.0, 20, 5),
    ("Fortune Maida 1kg", "8901030383112", "Atta & Flours", "pcs", 38.00, 45.00, 0.0, 25, 6),
    ("Fortune Sooji / Rawa 500g", "8901030383129", "Atta & Flours", "pcs", 28.00, 34.00, 0.0, 30, 6),
    ("Fortune Besan 500g", "8901030383136", "Atta & Flours", "pcs", 48.00, 58.00, 0.0, 40, 10),
    ("Daawat Rozana Super Basmati Rice 5kg", "8901537004128", "Rice & Grains", "pcs", 340.00, 395.00, 0.0, 18, 5),
    ("India Gate Basmati Rice Feast 1kg", "8901537001011", "Rice & Grains", "pcs", 85.00, 105.00, 0.0, 45, 10),
    ("Tata Sampann Unpolished Toor Dal 1kg", "8904043900213", "Dals & Pulses", "pcs", 155.00, 180.00, 0.0, 22, 6),
    ("Tata Sampann Moong Dal Dhuli 1kg", "8904043900220", "Dals & Pulses", "pcs", 130.00, 150.00, 0.0, 20, 5),
    ("Tata Sampann Chana Dal 1kg", "8904043900237", "Dals & Pulses", "pcs", 88.00, 105.00, 0.0, 28, 8),
    ("Loose Poha / Flattened Rice 1kg", "8900000000010", "Rice & Grains", "kg", 45.00, 55.00, 0.0, 50, 10),
    ("Loose Sugar / Chini 1kg", "8900000000011", "Sugar & Jaggery", "kg", 40.00, 46.00, 5.0, 120, 25),
    ("Kolhapur Pure Organic Gur / Jaggery 1kg", "8900000000012", "Sugar & Jaggery", "pcs", 65.00, 80.00, 0.0, 15, 5),

    # Oils & Ghee (5% and 12% GST)
    ("Fortune Sunlite Refined Sunflower Oil 1L", "8901030383792", "Edible Oils & Ghee", "ltr", 130.00, 145.00, 5.0, 45, 10),
    ("Fortune Kachi Ghani Mustard Oil 1L", "8901030383808", "Edible Oils & Ghee", "ltr", 140.00, 160.00, 5.0, 40, 10),
    ("Saffola Gold Pro Healthy Lifestyle Oil 1L", "8901088002010", "Edible Oils & Ghee", "ltr", 175.00, 198.00, 5.0, 25, 5),
    ("Gemini Refined Groundnut Oil 1L", "8901030383815", "Edible Oils & Ghee", "ltr", 165.00, 185.00, 5.0, 30, 8),
    ("Amul Pure Ghee 1L Pouch", "8901262010050", "Edible Oils & Ghee", "pcs", 580.00, 640.00, 12.0, 12, 4),
    ("Amul Cow Ghee 500ml Tin", "8901262010067", "Edible Oils & Ghee", "pcs", 320.00, 360.00, 12.0, 8, 3),

    # Spices & Salt
    ("Tata Salt Iodized 1kg", "8901030000014", "Spices & Condiments", "pcs", 24.00, 28.00, 0.0, 95, 20),
    ("Tata Salt Lite Low Sodium 1kg", "8901030000021", "Spices & Condiments", "pcs", 38.00, 45.00, 0.0, 25, 5),
    ("Everest Tikhalal Chilli Powder 200g", "8901786101016", "Spices & Condiments", "pcs", 82.00, 98.00, 5.0, 30, 6),
    ("Everest Turmeric / Haldi Powder 200g", "8901786102013", "Spices & Condiments", "pcs", 55.00, 68.00, 5.0, 35, 8),
    ("Everest Coriander / Dhaniya Powder 200g", "8901786103010", "Spices & Condiments", "pcs", 60.00, 72.00, 5.0, 30, 6),
    ("Everest Garam Masala 100g", "8901786104017", "Spices & Condiments", "pcs", 75.00, 90.00, 5.0, 25, 5),
    ("Catch Black Pepper Table Dispenser 100g", "8901199110115", "Spices & Condiments", "pcs", 95.00, 115.00, 5.0, 15, 4),
    ("Whole Jeera / Cumin Seeds 250g", "8900000000013", "Spices & Condiments", "pcs", 90.00, 110.00, 5.0, 18, 5),

    # Dairy & Beverages
    ("Amul Butter 100g", "8901262010111", "Dairy & Cold Storage", "pcs", 50.00, 58.00, 12.0, 45, 10),
    ("Amul Butter 500g", "8901262010128", "Dairy & Cold Storage", "pcs", 245.00, 275.00, 12.0, 15, 4),
    ("Amul Taaza Toned Milk 500ml", "8901262010135", "Dairy & Cold Storage", "pcs", 25.00, 27.00, 0.0, 60, 15),
    ("Amul Masti Dahi / Curd 400g", "8901262010142", "Dairy & Cold Storage", "pcs", 30.00, 35.00, 0.0, 20, 5),
    ("Amul Malai Fresh Paneer 200g", "8901262010159", "Dairy & Cold Storage", "pcs", 78.00, 90.00, 0.0, 14, 4),
    ("Red Label Strong Tea 500g", "8901030825018", "Tea, Coffee & Drinks", "pcs", 240.00, 280.00, 5.0, 30, 8),
    ("Tata Tea Gold 500g", "8901052002015", "Tea, Coffee & Drinks", "pcs", 260.00, 310.00, 5.0, 24, 6),
    ("Taj Mahal Premium Tea 250g", "8901030825025", "Tea, Coffee & Drinks", "pcs", 175.00, 205.00, 5.0, 16, 4),
    ("Nescafe Classic Coffee 50g Glass Jar", "8901058851013", "Tea, Coffee & Drinks", "pcs", 160.00, 185.00, 18.0, 20, 5),
    ("BRU Instant Coffee 100g Pouch", "8901030361011", "Tea, Coffee & Drinks", "pcs", 185.00, 215.00, 18.0, 15, 4),

    # Snacks, Noodles & Biscuits
    ("Maggi 2-Minute Masala Noodles 70g", "8901058852331", "Snacks & Instant Food", "pcs", 12.00, 14.00, 12.0, 150, 30),
    ("Maggi 2-Minute Masala Noodles 4-Pack 280g", "8901058852348", "Snacks & Instant Food", "pcs", 48.00, 56.00, 12.0, 45, 10),
    ("Yippee Magic Masala Noodles 70g", "8901725121013", "Snacks & Instant Food", "pcs", 11.50, 14.00, 12.0, 60, 15),
    ("Parle-G Original Glucose Biscuits 800g", "8901719101014", "Biscuits & Bakery", "pcs", 72.00, 85.00, 18.0, 50, 12),
    ("Britannia Good Day Butter Cookies 200g", "8901063012010", "Biscuits & Bakery", "pcs", 38.00, 45.00, 18.0, 40, 10),
    ("Britannia Marie Gold Biscuits 300g", "8901063012027", "Biscuits & Bakery", "pcs", 42.00, 50.00, 18.0, 35, 8),
    ("Cadbury Oreo Vanilla Creme Biscuits 120g", "8901233024018", "Biscuits & Bakery", "pcs", 32.00, 40.00, 18.0, 45, 10),
    ("Lay's India's Magic Masala 50g", "8901491101013", "Snacks & Instant Food", "pcs", 17.00, 20.00, 12.0, 60, 15),
    ("Kurkure Masala Munch 85g", "8901491102010", "Snacks & Instant Food", "pcs", 17.00, 20.00, 12.0, 60, 15),
    ("Haldiram's Nagpur Aloo Bhujia 200g", "8904004401018", "Snacks & Instant Food", "pcs", 48.00, 58.00, 12.0, 35, 8),
    ("Haldiram's Plain Bhujia Sev 200g", "8904004401025", "Snacks & Instant Food", "pcs", 45.00, 55.00, 12.0, 25, 6),

    # Chocolates & Sweets (28% GST)
    ("Cadbury Dairy Milk Silk Chocolate 60g", "8901233011018", "Chocolates & Sweets", "pcs", 65.00, 80.00, 28.0, 30, 8),
    ("Nestle KitKat 4-Finger Wafer Bar 38g", "8901058853017", "Chocolates & Sweets", "pcs", 24.00, 30.00, 28.0, 50, 12),
    ("Cadbury 5 Star Chocolate 40g", "8901233012015", "Chocolates & Sweets", "pcs", 16.00, 20.00, 28.0, 40, 10),
    ("Haldiram's Rasgulla 1kg Tin", "8904004402015", "Chocolates & Sweets", "pcs", 185.00, 230.00, 12.0, 12, 3),

    # Personal Care & Toiletries (18% GST)
    ("Dettol Original Bathing Soap 125g", "8901396328102", "Personal Care", "pcs", 46.00, 56.00, 18.0, 45, 10),
    ("Lifebuoy Total Germ Protection Soap 125g", "8901030381019", "Personal Care", "pcs", 34.00, 42.00, 18.0, 40, 10),
    ("Dove Cream Beauty Bathing Bar 100g", "8901030382016", "Personal Care", "pcs", 62.00, 75.00, 18.0, 25, 5),
    ("Clinic Plus Strong & Long Shampoo 340ml", "8901030383013", "Personal Care", "pcs", 165.00, 199.00, 18.0, 18, 5),
    ("Head & Shoulders Anti-Dandruff Cool Menthol 180ml", "8901314010011", "Personal Care", "pcs", 170.00, 210.00, 18.0, 15, 4),
    ("Colgate Strong Teeth Toothpaste 200g", "8901314020010", "Personal Care", "pcs", 95.00, 115.00, 18.0, 30, 8),
    ("Sensodyne Fresh Gel Sensitive Teeth 150g", "8901571010017", "Personal Care", "pcs", 185.00, 225.00, 18.0, 14, 4),
    ("Dettol Antiseptic Liquid 250ml", "8901396329017", "Personal Care", "pcs", 135.00, 162.00, 18.0, 20, 5),

    # Household & Detergents (18% GST)
    ("Surf Excel Easy Wash Detergent Powder 1kg", "8901030881014", "Cleaning & Household", "pcs", 125.00, 148.00, 18.0, 35, 8),
    ("Ariel Matic Front Load Detergent 1kg", "8901314030019", "Cleaning & Household", "pcs", 215.00, 255.00, 18.0, 18, 4),
    ("Rin Detergent Bar 250g", "8901030882011", "Cleaning & Household", "pcs", 22.00, 26.00, 18.0, 60, 15),
    ("Vim Dishwash Bar 300g with Scrubber", "8901030883018", "Cleaning & Household", "pcs", 26.00, 32.00, 18.0, 50, 12),
    ("Pril Dishwash Liquid Lime 425ml", "8901234050013", "Cleaning & Household", "pcs", 95.00, 115.00, 18.0, 22, 5),
    ("Harpic Power Plus Toilet Cleaner 500ml", "8901396331010", "Cleaning & Household", "pcs", 82.00, 99.00, 18.0, 30, 8),
    ("Lizol Disinfectant Floor Cleaner Citrus 500ml", "8901396332017", "Cleaning & Household", "pcs", 85.00, 105.00, 18.0, 28, 6),
    ("Good Knight Gold Flash Liquid Mosquito Refill", "8901023010018", "Cleaning & Household", "pcs", 72.00, 88.00, 18.0, 35, 8),
    ("Odonil Room Air Freshener Lavender 50g", "8901207010014", "Cleaning & Household", "pcs", 52.00, 65.00, 18.0, 25, 5),
]

# 2. Neighborhood Customers
KIRANA_CUSTOMERS = [
    ("Sharma Ji (Flat 204)", "+91 98111 22334", "B-204, Shanti Apartments"),
    ("Rajesh Verma (Teacher)", "+91 98222 33445", "House 45, Street No. 3"),
    ("Sunita Devi (Tailor)", "+91 98333 44556", "Near Shiv Mandir, Main Gali"),
    ("Dr. Amit Gupta (Clinic)", "+91 98444 55667", "Gupta Clinic, Market Complex"),
    ("Pooja Patel (Hostel)", "+91 98555 66778", "Plot 12, Girls PG Hostel"),
    ("Ramesh Chand (Postman)", "+91 98666 77889", "Quarter 5B, Railway Colony"),
    ("Vikram Singh (Gym Owner)", "+91 98777 88990", "Iron Gym, 1st Floor"),
    ("Ananya Roy (Software Eng)", "+91 98888 99001", "C-301, Greenwood Society"),
    ("Mohd. Tariq (Bakery)", "+91 98999 00112", "Shop 8, Daily Bakes"),
    ("Kavitha Iyer (Teacher)", "+91 98000 11223", "Flat 102, Kaveri Block"),
]


def seed_rich_kirana_database(db_path=None):
    """Populate full kirana inventory, customer base, and historical invoices."""
    print("Seeding full Kirana store inventory...")
    conn = get_connection(db_path)

    # 1. Clear previous sample products to avoid duplicate barcode errors
    with conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM bill_items")
        cur.execute("DELETE FROM stock_log")
        cur.execute("DELETE FROM bills")
        cur.execute("DELETE FROM products")
        cur.execute("DELETE FROM customers")

    # 2. Insert Products
    product_ids = []
    product_map = {}
    for item in KIRANA_CATALOG:
        name, barcode, cat, unit, pp, sp, gst, stock, min_stock = item
        pid = add_product(
            name=name,
            selling_price_paise=rupees_to_paise(sp),
            purchase_price_paise=rupees_to_paise(pp),
            barcode=barcode,
            category=cat,
            unit=unit,
            gst_rate=gst,
            stock_qty=float(stock),
            min_stock_qty=float(min_stock),
            db_path=db_path
        )
        product_ids.append(pid)
        product_map[pid] = {
            "id": pid,
            "name": name,
            "selling_price_paise": rupees_to_paise(sp),
            "unit": unit,
            "gst_rate": gst,
            "stock_qty": float(stock)
        }

    print(f"Inserted {len(product_ids)} retail items across 9 categories.")

    # 3. Insert Customers
    customer_ids = []
    for c_name, c_phone, c_addr in KIRANA_CUSTOMERS:
        cid = add_customer(name=c_name, phone=c_phone, address=c_addr, db_path=db_path)
        customer_ids.append(cid)

    print(f"Inserted {len(customer_ids)} neighborhood customer accounts.")

    # 4. Generate Historical Invoices over the past 25 days
    print("Simulating realistic past retail sales...")
    payment_modes = ["cash", "cash", "upi", "upi", "upi", "card", "credit"]

    total_bills_created = 0
    now = datetime.now()

    for day_offset in range(25, -1, -1):
        bill_date = now - timedelta(days=day_offset, hours=random.randint(1, 10), minutes=random.randint(5, 55))
        # 2 to 6 bills per day
        bills_today = random.randint(3, 7) if day_offset < 10 else random.randint(2, 5)

        for _ in range(bills_today):
            # Pick random customer or walk-in (40% walk-in)
            cust_id = random.choice(customer_ids) if random.random() > 0.4 else None
            pay_mode = "credit" if cust_id and random.random() < 0.25 else random.choice(payment_modes)

            # Pick 2 to 5 random products for cart
            selected_pids = random.sample(product_ids, random.randint(2, 5))
            cart = []
            for p_id in selected_pids:
                p_info = product_map[p_id]
                qty = float(random.choice([1, 1, 1, 2, 2, 3]))
                cart.append({
                    "id": p_info["id"],
                    "name": p_info["name"],
                    "selling_price_paise": p_info["selling_price_paise"],
                    "unit": p_info["unit"],
                    "gst_rate": p_info["gst_rate"],
                    "quantity": qty
                })

            # Small occasional discount
            disc_type = "Fixed (₹)"
            disc_val = float(random.choice([0, 0, 0, 10, 15, 20]))

            try:
                bill_res = checkout_bill(
                    customer_id=cust_id,
                    payment_mode=pay_mode,
                    cart_items=cart,
                    discount_type=disc_type,
                    discount_val=disc_val,
                    created_by=1,
                    db_path=db_path
                )
                total_bills_created += 1

                # Backdate the bill in database for realistic timeline
                with conn:
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE bills SET bill_date = ? WHERE id = ?",
                        (bill_date.strftime("%Y-%m-%d %H:%M:%S"), bill_res["bill_id"])
                    )

            except Exception:
                pass  # Skip if stock momentarily insufficient

    # Add a realistic payment settlement for one of the credit customers
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT id, credit_balance_paise FROM customers WHERE credit_balance_paise > 50000 LIMIT 1")
        row = cur.fetchone()
        if row:
            cid = row["id"]
            cur.execute("UPDATE customers SET credit_balance_paise = credit_balance_paise - 25000 WHERE id = ?", (cid,))

    conn.close()
    print(f"Database populated successfully with {len(product_ids)} products, {len(customer_ids)} customers, and {total_bills_created} historical invoices!")


if __name__ == "__main__":
    seed_rich_kirana_database()
