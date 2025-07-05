from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import logging


logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'techshop.db')}"
app.config['SECRET_KEY'] = 'your_secret_key_here'

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_vip = db.Column(db.Boolean, default=False)
    orders = db.relationship('Order', backref='user', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(50), nullable=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Processing')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product = db.relationship('Product')


def init_db():
    with app.app_context():
        db.create_all()

        if not Product.query.first():
            sample_products = [
                Product(name="Premium Laptop", price=999.99, category="Electronics",
                        description="High-performance laptop with 16GB RAM",
                        image_url="https://images.unsplash.com/photo-1496181133206-80ce9b88a853?ixlib=rb-4.0.3&auto=format&fit=crop&w=300&q=80"),
                Product(name="Wireless Headphones", price=149.99, category="Electronics",
                        description="Noise-cancelling headphones",
                        image_url="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?ixlib=rb-4.0.3&auto=format&fit=crop&w=300&q=80"),
            ]
            db.session.bulk_save_objects(sample_products)
            db.session.commit()
            print("📦 Sample products added.")

        if not User.query.filter_by(username="admin").first():
            test_user = User(
                username="admin",
                email="admin@test.com",
                password=generate_password_hash("admin123", method='pbkdf2:sha256')
            )
            db.session.add(test_user)
            db.session.commit()
            print("👤 Test user created: admin / admin123")

init_db()


@app.route('/')
def home():
    products = Product.query.limit(4).all()
    return render_template('home.html', products=products)

@app.route('/products')
def products():
    products = Product.query.all()
    return render_template('products.html', products=products)

@app.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    return render_template('product_detail.html', product=product)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password != confirm:
            flash("Passwords do not match", "danger")
            return redirect(url_for('register'))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists", "danger")
            return redirect(url_for('register'))

        try:
            new_user = User(
                username=username,
                email=email,
                password=generate_password_hash(password, method='pbkdf2:sha256')
            )
            db.session.add(new_user)
            db.session.commit()
            flash("Registration successful! Please login.", "success")
            print(f"✅ Registered user: {username}")
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            print("❌ Error during registration:", e)
            flash("Error creating account. Please try again.", "danger")
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash("Login successful!", "success")
            return redirect(url_for('home'))
        else:
            flash("Invalid credentials", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for('home'))

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    cart_items = []
    total = 0

    for product_id, qty in cart.items():
        product = Product.query.get(int(product_id))
        if product:
            subtotal = qty * product.price
            cart_items.append({'product': product, 'quantity': qty, 'total': subtotal})
            total += subtotal

    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = request.form.get("product_id")
    quantity = int(request.form.get("quantity", 1))

    if 'cart' not in session:
        session['cart'] = {}

    session['cart'][product_id] = session['cart'].get(product_id, 0) + quantity
    flash("Added to cart!", "success")
    return redirect(url_for('product_detail', id=product_id))

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    if 'cart' in session and str(product_id) in session['cart']:
        del session['cart'][str(product_id)]
        flash("Item removed from cart", "info")
    return redirect(url_for('view_cart'))

@app.route('/update_cart', methods=['POST'])
def update_cart():
    product_id = request.form.get("product_id")
    quantity = int(request.form.get("quantity"))

    if 'cart' in session:
        if quantity > 0:
            session['cart'][product_id] = quantity
        else:
            session['cart'].pop(product_id, None)
        flash("Cart updated", "info")

    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        flash("Please login to checkout", "warning")
        return redirect(url_for('login'))

    cart = session.get('cart', {})
    if not cart:
        flash("Your cart is empty", "warning")
        return redirect(url_for('home'))

    try:
        total = sum(Product.query.get(int(pid)).price * qty for pid, qty in cart.items())
        order = Order(user_id=session['user_id'], total=total)
        db.session.add(order)
        db.session.flush()

        for pid, qty in cart.items():
            db.session.add(OrderItem(order_id=order.id, product_id=int(pid), quantity=qty))

        db.session.commit()
        session.pop('cart', None)
        flash("Order placed successfully!", "success")
        return render_template("order_confirmation.html", order_id=order.id)

    except Exception as e:
        db.session.rollback()
        print("❌ Checkout error:", e)
        flash("There was a problem processing your order.", "danger")
        return redirect(url_for('view_cart'))

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_at.desc()).all()
    return render_template("orders.html", orders=orders)

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
