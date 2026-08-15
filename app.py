from flask import Flask, render_template, request, redirect, session, url_for, flash
import pandas as pd
import csv
import json 
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# File path
PRODUCTS_FILE = "data/products.xlsx"
INSTITUTES_FILE = 'institutions.json'
USERS_CSV = 'data/users.csv'

# Ensure the CSV file exists with headers
if not os.path.exists(USERS_CSV):
    with open(USERS_CSV, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['email', 'password', 'role'])  # header row

# ----------------- ROUTES -----------------

@app.route('/')
def home():
    if 'email' not in session:
        return redirect(url_for('login'))

    role = session.get('role')
    if role == 'buyer':
        return redirect(url_for('customer_dashboard'))
    elif role == 'seller':
        return redirect(url_for('farmer_dashboard'))
    else:
        return "Invalid role"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        role = request.form['role'].strip()

        df = pd.read_csv(USERS_CSV)
        user = df[(df['email'] == email) & (df['password'] == password) & (df['role'] == role)]

        if not user.empty:
            session['email'] = email
            session['role'] = role
            return redirect(url_for('home'))
        else:
            flash("Invalid email, password, or role.")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']

        if password != confirm_password:
            flash("Passwords do not match")
            return render_template('register.html')

        # Check if email already exists
        with open(USERS_CSV, mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['email'] == email:
                    flash("Email already registered")
                    return render_template('register.html')

        # Append new user
        with open(USERS_CSV, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([email, password, role])

        flash("Registration successful! Please log in.")
        return redirect(url_for('login'))

    return render_template('register.html')
@app.route('/farmers')
def view_farmers():
    if not os.path.exists(PRODUCTS_FILE):
        return "<h3>No farmer data available.</h3>"

    df = pd.read_excel(PRODUCTS_FILE)
    farmer_df = df[['Farmer Name', 'Farmer Location', 'Phone Number', 'Farmer Email']].drop_duplicates()
    farmers = farmer_df.to_dict(orient='records')
    return render_template('farmers.html', farmers=farmers)

@app.route('/institutions', methods=['GET', 'POST'])
def institutions():
    df = pd.read_excel(PRODUCTS_FILE)

    # Extract unique farmer names & emails
    farmers = df[['Farmer Name', 'Farmer Email']].drop_duplicates().to_dict(orient='records')

    if request.method == 'POST':
        form_data = {
            "institution": request.form['institute_name'],
            "email": request.form['contact_email'],
            "phone": request.form['phone'],
            "farmer_email": request.form['farmer_email'],
            "visit_date": request.form['visit_date'],
            "timestamp": datetime.now().isoformat()
        }

        # Load or create institution bookings
        inst_file = 'institution_bookings.json'
        if os.path.exists(inst_file):
            with open(inst_file, 'r') as f:
                inst_data = json.load(f)
        else:
            inst_data = []

        inst_data.append(form_data)

        with open(inst_file, 'w') as f:
            json.dump(inst_data, f, indent=2)

        flash("Visit booked successfully and payment processed!")
        return redirect(url_for('institutions'))

    return render_template("institutions.html", farmers=farmers)

@app.route('/confirm-payment')
def confirm_payment():
    # This would simulate payment confirmation logic
    flash("Payment Successful! Booking Confirmed.")
    return redirect(url_for('institutions'))

@app.route('/categories')
def show_categories():
    df = pd.read_excel(PRODUCTS_FILE)
    df = df[df['Category'].notna()]

    grouped = df.groupby('Category')['Quantity Available'].sum().reset_index()
    categories = [
        {'name': row['Category'], 'total_qty': int(row['Quantity Available'])}
        for _, row in grouped.iterrows()
    ]
    return render_template('categories.html', categories=categories)

@app.route('/category/<category_name>')
def show_category_products(category_name):
    df = pd.read_excel(PRODUCTS_FILE)
    df = df[df['Category'].str.lower() == category_name.lower()]
    products = df.to_dict(orient='records')
    return render_template('categories_template.html', category_name=category_name, products=products)

@app.route('/customer/dashboard')
def customer_dashboard():
    email = session.get('email')
    if not email:
        flash("Please login to view dashboard.")
        return redirect(url_for('login'))

    # Load product data
    df = pd.read_excel(PRODUCTS_FILE)

    # Latest 6 products
    latest_products = df.sort_values(by='Product ID', ascending=False).head(6).to_dict(orient='records')

    # Top-selling products (based on some field, here using Quantity for demo)
    top_selling = df.sort_values(by='Sold', ascending=False).head(6).to_dict(orient='records') if 'Sold' in df.columns else []

    # Load orders.json
    customer_orders = []
    if os.path.exists('orders.json'):
        with open('orders.json', 'r') as f:
            orders_data = json.load(f)
            customer_orders = [o for o in orders_data if o['buyer_email'] == email]

    # Load notifications.json
    customer_notifications = []
    if os.path.exists('notifications.json'):
        with open('notifications.json', 'r') as f:
            notif_data = json.load(f)
            customer_notifications = notif_data.get(email, [])

    return render_template('customer_dashboard.html',
                           latest_products=latest_products,
                           top_selling=top_selling,
                           customer_orders=customer_orders,
                           notifications=customer_notifications)

@app.route('/product/<int:product_id>')
def single_product(product_id):
    df = pd.read_excel(PRODUCTS_FILE)
    df = df[df['Product ID'] == product_id]

    if df.empty:
        return "Product not found", 404

    product = df.iloc[0].to_dict()

    # Load reviews
    if os.path.exists('reviews.json'):
        with open('reviews.json', 'r') as f:
            all_reviews = json.load(f)
    else:
        all_reviews = {}

    product_reviews = all_reviews.get(str(product_id), [])

    # 🧑‍🌾 Extract farmer info from the product itself
    farmer = {
        'Name': product.get('Farmer Name', 'Unknown'),
        'Location': product.get('Farmer Location', 'Unknown'),
        'Email': product.get('Farmer Email', 'Unknown'),
        'Phone': product.get('Phone Number', 'Unknown')
    }

    return render_template('single_product.html',
                           product=product,
                           reviews=product_reviews,
                           farmer=farmer)

@app.route('/submit-feedback/<int:product_id>', methods=['POST'])
def submit_feedback(product_id):
    name = request.form.get('name')
    rating = request.form.get('rating')
    comment = request.form.get('comment')

    if not (name and rating and comment):
        return "All fields are required", 400

    review = {
        "name": name,
        "rating": int(rating),
        "comment": comment
    }

    if os.path.exists('reviews.json'):
        with open('reviews.json', 'r') as f:
            all_reviews = json.load(f)
    else:
        all_reviews = {}

    all_reviews.setdefault(str(product_id), []).append(review)

    with open('reviews.json', 'w') as f:
        json.dump(all_reviews, f, indent=2)

    return redirect(url_for('single_product', product_id=product_id))

@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    if 'email' not in session:
        flash("Please login to add to cart.")
        return redirect(url_for('login'))

    product_id = int(request.form['product_id'])
    quantity = int(request.form['quantity'])

    cart = session.get('cart', [])

    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] += quantity
            break
    else:
        cart.append({'product_id': product_id, 'quantity': quantity})

    session['cart'] = cart
    session.modified = True
    flash("Product added to cart!")
    return redirect(url_for('view_cart'))

@app.route('/cart')
def view_cart():
    cart = session.get('cart', [])
    if not cart:
        return render_template("cart.html", cart_items=[], total=0)

    df = pd.read_excel(PRODUCTS_FILE)
    cart_items = []

    for item in cart:
        product_row = df[df['Product ID'] == item['product_id']]
        if product_row.empty:
            continue
        product = product_row.iloc[0].to_dict()
        cart_items.append({
            'product_id': item['product_id'],
            'name': product['Product Name'],
            'price': product['Price (INR/kg/ltr)'],
            'quantity': item['quantity'],
            'subtotal': product['Price (INR/kg/ltr)'] * item['quantity'],
            'image': product['Image URL']
        })

    total_price = sum(item['subtotal'] for item in cart_items)
    return render_template("cart.html", cart_items=cart_items, total=total_price)


@app.route('/cart/clear')
def clear_cart():
    session.pop('cart', None)
    session.modified = True
    flash("Cart cleared!")
    return redirect(url_for('view_cart'))


@app.route('/cart/increase/<int:product_id>', methods=['POST'])
def increase_quantity(product_id):
    cart = session.get('cart', [])
    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] += 1
            break
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('view_cart'))


@app.route('/cart/decrease/<int:product_id>', methods=['POST'])
def decrease_quantity(product_id):
    cart = session.get('cart', [])
    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] -= 1
            if item['quantity'] <= 0:
                cart.remove(item)
            break
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('view_cart'))


@app.route('/cart/delete/<int:product_id>', methods=['POST'])
def delete_from_cart(product_id):
    cart = session.get('cart', [])
    cart = [item for item in cart if item['product_id'] != product_id]
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    # Always fetch from session at the start
    cart = session.get('cart', [])

    if not cart:
        flash("Your cart is empty!")
        return redirect(url_for('view_cart'))

    df = pd.read_excel(PRODUCTS_FILE)

    # Create cart_items and total — required for both GET and POST
    cart_items = []
    total = 0

    for item in cart:
        product_row = df[df['Product ID'] == item['product_id']]
        if product_row.empty:
            continue
        product = product_row.iloc[0].to_dict()
        subtotal = product['Price (INR/kg/ltr)'] * item['quantity']
        total += subtotal

        cart_items.append({
            'product_id': item['product_id'],
            'name': product['Product Name'],
            'price': product['Price (INR/kg/ltr)'],
            'quantity': item['quantity'],
            'subtotal': subtotal,
            'image': product['Image URL']
        })

    if request.method == 'POST':
        email = session.get('email', 'guest')

        # Load previous orders
        if os.path.exists('orders.json'):
            with open('orders.json', 'r') as f:
                orders_data = json.load(f)
        else:
            orders_data = []

        for item in cart_items:
            product_row = df[df['Product ID'] == item['product_id']]
            if product_row.empty:
                continue
            farmer_email = product_row.iloc[0]['Farmer Email']

            order = {
                "order_id": str(uuid.uuid4()),
                "product_id": item['product_id'],
                "product_name": item['name'],
                "quantity": item['quantity'],
                "price": item['price'],
                "subtotal": item['subtotal'],
                "buyer_email": email,
                "farmer_email": farmer_email,
                "timestamp": datetime.now().isoformat()
            }

            notify_farmer(farmer_email, order)
            notify_customer(email, order)
            orders_data.append(order)

            # Update stock in Excel
            df.loc[df['Product ID'] == item['product_id'], 'Quantity Available'] -= item['quantity']

        # Save Excel
        df.to_excel(PRODUCTS_FILE, index=False)

        # Save orders
        with open('orders.json', 'w') as f:
            json.dump(orders_data, f, indent=2)

        # Clear cart from session
        session['cart'] = []
        flash("Order placed successfully!")
        return redirect(url_for('view_cart'))

    # GET: Show confirmation screen
    return render_template('checkout.html', cart_items=cart_items, total=total)

def notify_farmer(farmer_email, order):
    notification = {
        "type": "New Order",
        "message": f"Order for {order['product_name']} ({order['quantity']} units) received from {order['buyer_email']}",
        "timestamp": datetime.now().isoformat()
    }

    store_notification(farmer_email, notification)


def notify_customer(customer_email, order):
    notification = {
        "type": "Order Confirmation",
        "message": f"You ordered {order['product_name']} ({order['quantity']} units) - Total ₹{order['subtotal']}",
        "timestamp": datetime.now().isoformat()
    }

    store_notification(customer_email, notification)


def store_notification(user_email, notification):
    notif_file = 'notifications.json'

    if os.path.exists(notif_file):
        with open(notif_file, 'r') as f:
            data = json.load(f)
    else:
        data = {}

    data.setdefault(user_email, []).append(notification)

    with open(notif_file, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/farmer/dashboard')
def farmer_dashboard():
    email = session.get('email')
    if not email:
        flash("Please login to view dashboard.")
        return redirect(url_for('login'))

    df = pd.read_excel(PRODUCTS_FILE)

    # Filter only this farmer’s products
    farmer_products = df[df['Farmer Email'] == email]

    # Top 5 ordered products by quantity (optional: sort using your own logic)
    if 'Sold' in farmer_products.columns:
        top_products = farmer_products.sort_values(by='Sold', ascending=False).head(5).to_dict(orient='records')
    else:
        top_products = farmer_products.head(5).to_dict(orient='records')

    # Load orders.json and filter orders for this farmer
    farmer_orders = []
    if os.path.exists('orders.json'):
        with open('orders.json', 'r') as f:
            all_orders = json.load(f)
            farmer_orders = [o for o in all_orders if o['farmer_email'] == email]

    # Load notifications.json
    farmer_notifications = []
    if os.path.exists('notifications.json'):
        with open('notifications.json', 'r') as f:
            notif_data = json.load(f)
            farmer_notifications = notif_data.get(email, [])

    farmer_name = farmer_products['Farmer Name'].iloc[0] if not farmer_products.empty else email

    return render_template("farmer_dashboard.html",
                           farmer_name=farmer_name,
                           top_products=top_products,
                           farmer_orders=farmer_orders,
                           notifications=farmer_notifications)

@app.route('/farmer/orders')
def farmer_orders():
    if session.get('role') != 'seller':
        return redirect(url_for('login'))

    email = session.get('email')
    orders = []

    if os.path.exists('orders.json'):
        with open('orders.json', 'r') as f:
            all_orders = json.load(f)
            orders = [order for order in all_orders if order['farmer_email'] == email]

    return render_template('farmer_orders.html', orders=orders)

@app.route('/farmer/institute-notifications')
def farmer_institute_notifications():
    if session.get('role') != 'seller':
        return redirect(url_for('login'))

    email = session.get('email')
    visits = []

    if os.path.exists('institution_bookings.json'):
        with open('institution_bookings.json', 'r') as f:
            all_bookings = json.load(f)
            visits = [b for b in all_bookings if b['farmer_email'] == email]

    return render_template('farmer_institute_notifications.html', visits=visits)

@app.route('/farmer/feedback')
def farmer_feedback():
    if session.get('role') != 'seller':
        return redirect(url_for('login'))

    email = session.get('email')
    feedbacks = []

    if os.path.exists('reviews.json') and os.path.exists(PRODUCTS_FILE):
        with open('reviews.json', 'r') as f:
            reviews = json.load(f)

        df = pd.read_excel(PRODUCTS_FILE)
        farmer_products = df[df['Farmer Email'] == email]
        product_ids = farmer_products['Product ID'].tolist()

        for pid in product_ids:
            product_reviews = reviews.get(str(pid), [])
            for review in product_reviews:
                feedbacks.append({
                    "product_id": pid,
                    "product_name": df[df['Product ID'] == pid].iloc[0]['Product Name'],
                    "review": review
                })

    return render_template('farmer_feedback.html', feedbacks=feedbacks)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        flash("Please log in.")
        return redirect(url_for('login'))

    email = session.get('email')
    role = session.get('role')

    name = location = phone = ''
    customer_location = ''

    # For farmers: Get full profile from Excel
    if role == 'seller' and os.path.exists(PRODUCTS_FILE):
        df = pd.read_excel(PRODUCTS_FILE)
        row = df[df['Farmer Email'] == email].iloc[0] if not df[df['Farmer Email'] == email].empty else None
        if row is not None:
            name = row.get('Farmer Name', '')
            location = row.get('Farmer Location', '')
            phone = row.get('Phone Number', '')

    # For customers: allow location + password update
    if role == 'buyer':
        if os.path.exists('customer_profiles.json'):
            with open('customer_profiles.json', 'r') as f:
                profiles = json.load(f)
        else:
            profiles = {}

        customer_data = profiles.get(email, {})
        customer_location = customer_data.get('location', '')

        if request.method == 'POST':
            new_location = request.form.get('location')
            new_password = request.form.get('new_password')

            profiles[email] = {
                "location": new_location,
                "password": new_password  # For now stored as plain text (you can hash later)
            }

            with open('customer_profiles.json', 'w') as f:
                json.dump(profiles, f, indent=2)

            flash("Profile updated successfully!")
            return redirect(url_for('profile'))

    return render_template('profile.html',
                           role=role,
                           user=email,
                           name=name,
                           location=location if role == 'seller' else customer_location,
                           phone=phone)

@app.route('/farmer/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if session.get('role') != 'seller':
        return redirect(url_for('login'))

    email = session.get('email')

    if request.method == 'POST':
        new_name = request.form['name']
        new_location = request.form['location']
        new_phone = request.form['phone']

        if os.path.exists(PRODUCTS_FILE):
            df = pd.read_excel(PRODUCTS_FILE)
            df.loc[df['Farmer Email'] == email, 'Farmer Name'] = new_name
            df.loc[df['Farmer Email'] == email, 'Farmer Location'] = new_location
            df.loc[df['Farmer Email'] == email, 'Phone Number'] = new_phone
            df.to_excel(PRODUCTS_FILE, index=False)

        flash("Profile updated successfully!")
        return redirect(url_for('farmer_dashboard'))

    if os.path.exists(PRODUCTS_FILE):
        df = pd.read_excel(PRODUCTS_FILE)
        profile_row = df[df['Farmer Email'] == email].iloc[0] if not df[df['Farmer Email'] == email].empty else None
        name = profile_row.get('Farmer Name', '') if profile_row is not None else ''
        location = profile_row.get('Farmer Location', '') if profile_row is not None else ''
        phone = profile_row.get('Phone Number', '') if profile_row is not None else ''
    else:
        name = location = phone = ''

    return render_template('edit_profile.html', name=name, location=location, phone=phone)

@app.route('/farmer/view-products')
def view_products():
    if session.get('role') != 'seller':
        return redirect(url_for('login'))

    email = session.get('email')
    df = pd.read_excel(PRODUCTS_FILE)
    farmer_products = df[df['Farmer Email'] == email].to_dict(orient='records')

    return render_template('viewproducts.html', products=farmer_products)

@app.route('/farmer/edit-product/<product_name>', methods=['GET', 'POST'])
def edit_product(product_name):
    if session.get('role') != 'seller':
        return redirect(url_for('login'))

    email = session.get('email')

    if not os.path.exists(PRODUCTS_FILE):
        return f"<h3>Product data not found</h3>"

    df = pd.read_excel(PRODUCTS_FILE)

    # Get the product for this farmer by name and email
    product_row = df[(df['Product Name'] == product_name) & (df['Farmer Email'] == email)]
    if product_row.empty:
        return "<h3>Product not found or you don't have permission</h3>"

    index = product_row.index[0]

    if request.method == 'POST':
        df.at[index, 'Product Name'] = request.form['item_name']
        df.at[index, 'Category'] = request.form['category']
        df.at[index, 'Quantity Available'] = int(request.form['quantity'])
        df.at[index, 'Price (INR/kg/ltr)'] = float(request.form['price'])
        df.at[index, 'Description'] = request.form['description']

        # Check if a new image was uploaded
        image_file = request.files.get('image_file')
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            image_path = os.path.join('static', filename)
            image_file.save(image_path)
            df.at[index, 'Image URL'] = image_path.replace("\\", "/")

        df.to_excel(PRODUCTS_FILE, index=False)
        flash("Product updated successfully!")
        return redirect(url_for('view_products'))

    product_data = df.loc[index].to_dict()
    return render_template('edit_product.html', product=product_data)

@app.route('/farmer/add-product', methods=['GET', 'POST'])
def add_product():
    if session.get('role') != 'seller':
        return render_template('add_product.html')

    if request.method == 'POST':
        item_name = request.form['item_name']
        category = request.form['category']
        quantity = request.form['quantity']
        price = request.form['price']
        description = request.form['description']
        image_file = request.files['image_file']

        image_url = ''
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            image_path = os.path.join('static', filename)
            image_file.save(image_path)
            image_url = image_path.replace("\\", "/")  # 🔥 Fix path here!

        farmer_id = session.get('email')
        farmer_name = session.get('name', 'Unknown')
        farmer_location = session.get('location', 'Unknown')
        phone = session.get('phone', 'Unknown')

        if os.path.exists(PRODUCTS_FILE):
            df = pd.read_excel(PRODUCTS_FILE)
        else:
            df = pd.DataFrame(columns=[
                "Product ID", "Product Name", "Category", "Price (INR/kg/ltr)", "Description",
                "Quantity Available", "Image URL", "Farmer ID", "Farmer Name", "Farmer Location", "Phone Number", "Farmer Email"
            ])

        product_id = len(df) + 1

        new_row = {
            "Product ID": product_id,
            "Product Name": item_name,
            "Category": category,
            "Price (INR/kg/ltr)": float(price),
            "Description": description,
            "Quantity Available": int(quantity),
            "Image URL": image_url, 
            "Farmer Name": farmer_name,
            "Farmer Location": farmer_location,
            "Phone Number": phone,
            "Farmer Email": farmer_id
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(PRODUCTS_FILE, index=False)

        flash("Product added successfully!")
        return redirect(url_for('farmer_dashboard'))

    return render_template('add_product.html')

@app.route('/farmer/delete-product/<product_name>', methods=['POST'])
def delete_product(product_name):
    if session.get('role') != 'seller':
        return redirect(url_for('login'))

    email = session.get('email')

    if os.path.exists(PRODUCTS_FILE):
        df = pd.read_excel(PRODUCTS_FILE)
        # Only delete product that belongs to current farmer
        df = df[~((df['Product Name'] == product_name) & (df['Farmer Email'] == email))]
        df.to_excel(PRODUCTS_FILE, index=False)
        flash("Product deleted successfully!")

    return redirect(url_for('view_products'))

if __name__ == '__main__':
    app.run(debug=True)
