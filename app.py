from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pyodbc
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Khóa bí mật cho session

# Cấu hình upload ảnh
UPLOAD_FOLDER = 'static/uploads/book_images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Hàm kiểm tra định dạng file ảnh
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Cấu hình kết nối SQL Server
def get_db_connection():
    try:
        conn = pyodbc.connect(
            'DRIVER={SQL Server};'
            'SERVER=MSI\SERVER;'  # Thay bằng tên server của bạn
            'DATABASE=BookStore;'
            'UID=sa;'        # Thay bằng tên người dùng SQL Server
            'PWD=12'         # Thay bằng mật khẩu
        )
        return conn
    except pyodbc.Error as e:
        print(f"Không thể kết nối đến cơ sở dữ liệu: {e}")
        return None

# Hàm chuyển đổi chuỗi created_at thành datetime
def parse_datetime(date_str):
    if date_str:
        try:
            return datetime.strptime(str(date_str), '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            return None
    return None

# Route trang chủ
@app.route('/')
def index():
    conn = get_db_connection()
    if conn:
        conn.close()
        return render_template('index.html', message="Hello World! Kết nối database thành công.")
    return render_template('index.html', message="Hello World! Không thể kết nối database.")

# Route đăng nhập
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, role, username, email FROM Users WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()
            conn.close()

            if user:
                session['user_id'] = user[0]
                session['role'] = user[1]
                session['username'] = user[2]
                session['email'] = user[3]
                if user[1] in ['Qly', 'Nvien']:
                    return redirect(url_for('dashboard'))
                elif user[1] == 'KH':
                    return redirect(url_for('home'))
            else:
                flash("Tên đăng nhập hoặc mật khẩu không đúng!", "danger")
        else:
            flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
    return render_template('login.html')

# Route trang dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Vui lòng đăng nhập để truy cập!", "warning")
        return redirect(url_for('login'))
    if session['role'] == 'KH':
        flash("Bạn không có quyền truy cập trang này!", "danger")
        return redirect(url_for('home'))

    active_menu = request.args.get('menu', 'overview')
    data = {}
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if active_menu == 'accounts':
            # Phân trang
            page = int(request.args.get('page', 1))
            per_page = 10
            offset = (page - 1) * per_page

            # Lấy tổng số tài khoản
            cursor.execute("SELECT COUNT(*) FROM Users")
            total_accounts = cursor.fetchone()[0]
            total_pages = (total_accounts + per_page - 1) // per_page

            # Lấy danh sách tài khoản với phân trang
            cursor.execute("SELECT user_id, username, role, created_at, status FROM Users ORDER BY user_id OFFSET ? ROWS FETCH NEXT ? ROWS ONLY", (offset, per_page))
            accounts = cursor.fetchall()

            # Chuyển đổi created_at thành datetime và định dạng
            formatted_accounts = []
            for account in accounts:
                created_at = parse_datetime(account[3])
                formatted_account = list(account)
                formatted_account[3] = created_at.strftime('%d/%m/%Y') if created_at else 'N/A'
                formatted_accounts.append(formatted_account)

            data['accounts'] = formatted_accounts
            data['page'] = page
            data['total_pages'] = total_pages
            data['total_accounts'] = total_accounts
    except pyodbc.Error as e:
        flash(f"Lỗi khi truy vấn dữ liệu: {e}", "danger")
    finally:
        if conn:
            conn.close()

    return render_template('dashboard.html', active_menu=active_menu, data=data)

# Route thêm tài khoản
@app.route('/add_account', methods=['GET', 'POST'])
def add_account():
    if 'user_id' not in session or session['role'] not in ['Qly', 'Nvien']:
        flash("Bạn không có quyền truy cập!", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Kiểm tra username đã tồn tại
            cursor.execute("SELECT COUNT(*) FROM Users WHERE username = ?", (username,))
            if cursor.fetchone()[0] > 0:
                return jsonify({'error': 'Tên đăng nhập đã tồn tại!', 'field': 'username'}), 400

            # Kiểm tra email đã tồn tại
            cursor.execute("SELECT COUNT(*) FROM Users WHERE email = ?", (email,))
            if cursor.fetchone()[0] > 0:
                return jsonify({'error': 'Email đã tồn tại!', 'field': 'email'}), 400

            # Nếu không có lỗi, thêm tài khoản
            cursor.execute(
                "INSERT INTO Users (username, password, role, email, phone, address, created_at, status) VALUES (?, ?, ?, ?, ?, ?, GETDATE(), ?)",
                (username, password, role, email, phone, address, 'Active')
            )
            conn.commit()
            return jsonify({'success': 'Thêm tài khoản thành công!'}), 200
        except pyodbc.Error as e:
            return jsonify({'error': f'Lỗi khi thêm tài khoản: {e}'}), 500
        finally:
            if conn:
                conn.close()

    return render_template('add_account.html')

# Route sửa tài khoản
@app.route('/edit_account/<int:user_id>', methods=['GET', 'POST'])
def edit_account(user_id):
    if 'user_id' not in session or session['role'] not in ['Qly', 'Nvien']:
        flash("Bạn không có quyền truy cập!", "danger")
        return redirect(url_for('login'))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.method == 'POST':
            username = request.form['username']
            role = request.form['role']
            email = request.form['email']
            phone = request.form['phone']
            address = request.form['address']
            status = request.form['status']

            # Kiểm tra username đã tồn tại (ngoại trừ chính tài khoản đang sửa)
            cursor.execute("SELECT COUNT(*) FROM Users WHERE username = ? AND user_id != ?", (username, user_id))
            if cursor.fetchone()[0] > 0:
                return jsonify({'error': 'Tên đăng nhập đã tồn tại!', 'field': 'username'}), 400

            # Kiểm tra email đã tồn tại (ngoại trừ chính tài khoản đang sửa)
            cursor.execute("SELECT COUNT(*) FROM Users WHERE email = ? AND user_id != ?", (email, user_id))
            if cursor.fetchone()[0] > 0:
                return jsonify({'error': 'Email đã tồn tại!', 'field': 'email'}), 400

            # Nếu không có lỗi, cập nhật tài khoản
            cursor.execute(
                "UPDATE Users SET username = ?, role = ?, email = ?, phone = ?, address = ?, status = ? WHERE user_id = ?",
                (username, role, email, phone, address, status, user_id)
            )
            conn.commit()
            return jsonify({'success': 'Cập nhật tài khoản thành công!'}), 200
        else:
            cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                flash("Tài khoản không tồn tại!", "danger")
                return redirect(url_for('dashboard', menu='accounts'))
            return render_template('edit_account.html', user=user)
    except pyodbc.Error as e:
        return jsonify({'error': f'Lỗi: {e}'}), 500
    finally:
        if conn:
            conn.close()

# Route khóa/mở khóa tài khoản
@app.route('/toggle_status/<int:user_id>', methods=['POST'])
def toggle_status(user_id):
    if 'user_id' not in session or session['role'] not in ['Qly', 'Nvien']:
        return jsonify({'error': 'Bạn không có quyền truy cập!'}), 403

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM Users WHERE user_id = ?", (user_id,))
        current_status = cursor.fetchone()

        if current_status:
            new_status = 'Lock' if current_status[0] == 'Active' else 'Active'
            cursor.execute("UPDATE Users SET status = ? WHERE user_id = ?", (new_status, user_id))
            conn.commit()
            return jsonify({'success': f'Đã { "khóa" if new_status == "Lock" else "mở khóa" } tài khoản!', 'new_status': new_status}), 200
        else:
            return jsonify({'error': 'Tài khoản không tồn tại!'}), 404
    except pyodbc.Error as e:
        return jsonify({'error': f'Lỗi: {e}'}), 500
    finally:
        if conn:
            conn.close()

# Route xem chi tiết tài khoản
@app.route('/account_detail/<int:user_id>')
def account_detail(user_id):
    if 'user_id' not in session or session['role'] not in ['Qly', 'Nvien']:
        flash("Bạn không có quyền truy cập!", "danger")
        return redirect(url_for('login'))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            flash("Tài khoản không tồn tại!", "danger")
            return redirect(url_for('dashboard', menu='accounts'))

        # Chuyển đổi created_at thành chuỗi định dạng
        formatted_user = list(user)
        created_at = parse_datetime(user[8])  # created_at ở vị trí 8
        formatted_user[8] = created_at.strftime('%d/%m/%Y %H:%M:%S') if created_at else 'N/A'
        # Status ở vị trí 7, không cần định dạng thêm
    except pyodbc.Error as e:
        flash(f"Lỗi: {e}", "danger")
        return redirect(url_for('dashboard', menu='accounts'))
    finally:
        if conn:
            conn.close()

    return render_template('account_detail.html', user=formatted_user)

# Route trang home (dành cho KH)
@app.route('/home')
def home():
    if 'user_id' not in session:
        flash("Vui lòng đăng nhập để truy cập!", "warning")
        return redirect(url_for('login'))
    return render_template('home.html')

# Route đăng xuất
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('username', None)
    session.pop('email', None)
    flash("Đã đăng xuất thành công!", "success")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



#SweetAlert2