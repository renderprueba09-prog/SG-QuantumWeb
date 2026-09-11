from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura'

# Configuración robusta de la carpeta de subidas usando la ruta raíz de la aplicación
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Tabla de usuarios (Administradores y Motorizados)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_completo TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL -- 'admin' o 'motorizado'
        )
    ''')
    
    # Tabla de entregas / documentos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entregas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_documento TEXT NOT NULL,
            numero_documento TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            direccion TEXT NOT NULL,
            motorizado_id INTEGER,
            estado TEXT DEFAULT 'pendiente', -- 'pendiente' o 'entregado'
            tipo_entrega TEXT,
            parentesco TEXT,
            nombre_receptor TEXT,
            dni_receptor TEXT,
            celular_receptor TEXT,
            foto_casa TEXT,
            foto_calle TEXT,
            foto_cargo_o_preaviso TEXT,
            firma TEXT,
            FOREIGN KEY (motorizado_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Agregar columnas faltantes de forma segura si la tabla ya existía previamente
    columnas_nuevas = [
        ("tipo_entrega", "TEXT"),
        ("parentesco", "TEXT"),
        ("nombre_receptor", "TEXT"),
        ("dni_receptor", "TEXT"),
        ("celular_receptor", "TEXT"),
        ("foto_casa", "TEXT"),
        ("foto_calle", "TEXT"),
        ("foto_cargo_o_preaviso", "TEXT"),
        ("firma", "TEXT")
    ]
    
    for col_nombre, col_tipo in columnas_nuevas:
        try:
            cursor.execute(f"ALTER TABLE entregas ADD COLUMN {col_nombre} {col_tipo}")
        except sqlite3.OperationalError:
            pass # La columna ya existe
    
    # Crear admin por defecto si no existe
    cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios (nombre_completo, username, password, rol) VALUES (?, ?, ?, ?)",
                       ('Administrador General', 'admin', '1234', 'admin'))
        
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['usuario']
        password = request.form['password']
        
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['rol'] = user['rol']
            session['nombre'] = user['nombre_completo']
            
            if user['rol'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('motorizado_dashboard'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
            
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if 'rol' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT e.*, u.nombre_completo as motorizado_nombre 
        FROM entregas e 
        LEFT JOIN usuarios u ON e.motorizado_id = u.id 
        WHERE e.estado = 'pendiente'
    ''')
    pendientes = cursor.fetchall()
    
    cursor.execute('''
        SELECT e.*, u.nombre_completo as motorizado_nombre 
        FROM entregas e 
        LEFT JOIN usuarios u ON e.motorizado_id = u.id 
        WHERE e.estado = 'entregado'
    ''')
    entregadas = cursor.fetchall()
    
    conn.close()
    return render_template('admin_dashboard.html', pendientes=pendientes, entregadas=entregadas)

@app.route('/admin/limpiar-sistema', methods=['POST'])
def limpiar_sistema():
    if 'rol' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))
        
    try:
        # 1. Vaciar y eliminar todos los archivos físicos dentro de static/uploads
        if os.path.exists(app.config['UPLOAD_FOLDER']):
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)

        # 2. Vaciar tablas de la base de datos de manera limpia
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Borrar todas las entregas de prueba
        cursor.execute("DELETE FROM entregas")
        
        # Borrar a todos los usuarios excepto al administrador principal ('admin')
        cursor.execute("DELETE FROM usuarios WHERE username != 'admin'")
        
        conn.commit()
        conn.close()

        flash('Sistema limpiado correctamente: registros de base de datos y archivos de prueba eliminados.', 'success')
    except Exception as e:
        flash(f'Error al limpiar el sistema: {str(e)}', 'danger')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/motorizados', methods=['GET', 'POST'])
def gestionar_motorizados():
    if 'rol' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        nombre = request.form['nombre_completo']
        username = request.form['username']
        password = request.form['password']
        
        try:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO usuarios (nombre_completo, username, password, rol) VALUES (?, ?, ?, 'motorizado')",
                           (nombre, username, password))
            conn.commit()
            conn.close()
            flash('Motorizado creado exitosamente', 'success')
        except sqlite3.IntegrityError:
            flash('El nombre de usuario ya existe', 'danger')
            
        return redirect(url_for('gestionar_motorizados'))
        
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE rol = 'motorizado'")
    motorizados = cursor.fetchall()
    conn.close()
    
    return render_template('admin_motorizados.html', motorizados=motorizados)

@app.route('/admin/motorizado/eliminar/<int:id>')
def eliminar_motorizado(id):
    if 'rol' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = ? AND rol = 'motorizado'", (id,))
    conn.commit()
    conn.close()
    flash('Motorizado eliminado', 'success')
    return redirect(url_for('gestionar_motorizados'))

@app.route('/admin/entregas', methods=['GET', 'POST'])
def gestionar_entregas():
    if 'rol' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if request.method == 'POST':
        tipo_doc = request.form['tipo_documento']
        nro_doc = request.form['numero_documento']
        destinatario = request.form['destinatario']
        direccion = request.form['direccion']
        motorizado_id = request.form['motorizado_id']
        
        cursor.execute('''
            INSERT INTO entregas (tipo_documento, numero_documento, destinatario, direccion, motorizado_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (tipo_doc, nro_doc, destinatario, direccion, motorizado_id))
        conn.commit()
        conn.close()
        flash('Entrega creada y asignada correctamente', 'success')
        return redirect(url_for('gestionar_entregas'))
        
    cursor.execute("SELECT * FROM usuarios WHERE rol = 'motorizado'")
    motorizados = cursor.fetchall()
    
    cursor.execute('''
        SELECT e.*, u.nombre_completo as motorizado_nombre 
        FROM entregas e 
        LEFT JOIN usuarios u ON e.motorizado_id = u.id
    ''')
    entregas = cursor.fetchall()
    conn.close()
    
    return render_template('admin_entregas.html', motorizados=motorizados, entregas=entregas)

@app.route('/admin/entrega/eliminar/<int:id>')
def eliminar_entrega(id):
    if 'rol' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM entregas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash('Entrega eliminada correctamente', 'success')
    return redirect(url_for('gestionar_entregas'))

@app.route('/motorizado')
def motorizado_dashboard():
    if 'rol' not in session or session['rol'] != 'motorizado':
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM entregas WHERE motorizado_id = ? AND estado = 'pendiente'", (session['user_id'],))
    pendientes = cursor.fetchall()
    
    cursor.execute("SELECT * FROM entregas WHERE motorizado_id = ? AND estado = 'entregado'", (session['user_id'],))
    completadas = cursor.fetchall()
    
    conn.close()
    
    return render_template('motorizado_dashboard.html', nombre_motorizado=session['nombre'], pendientes=pendientes, completadas=completadas)

@app.route('/motorizado/detalle/<int:entrega_id>')
def motorizado_detalle(entrega_id):
    if 'rol' not in session or session['rol'] != 'motorizado':
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM entregas WHERE id = ? AND motorizado_id = ? AND estado = 'entregado'", (entrega_id, session['user_id']))
    entrega = cursor.fetchone()
    conn.close()
    
    if not entrega:
        flash('Entrega no encontrada o no autorizada', 'danger')
        return redirect(url_for('motorizado_dashboard'))
        
    return render_template('motorizado_detalle.html', entrega=entrega, nombre_motorizado=session['nombre'])

@app.route('/motorizado/entregar/<int:entrega_id>', methods=['GET', 'POST'])
def registrar_entrega(entrega_id):
    if 'rol' not in session or session['rol'] != 'motorizado':
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM entregas WHERE id = ? AND motorizado_id = ? AND estado = 'pendiente'", 
                   (entrega_id, session['user_id']))
    entrega = cursor.fetchone()
    
    if not entrega:
        conn.close()
        flash('Entrega no encontrada o no autorizada', 'danger')
        return redirect(url_for('motorizado_dashboard'))
        
    if request.method == 'POST':
        tipo_entrega = request.form.get('tipo_entrega')
        parentesco = request.form.get('parentesco')
        nombre_receptor = request.form.get('recibido_por') or request.form.get('nombre_receptor')
        dni_receptor = request.form.get('dni_receptor')
        celular_receptor = request.form.get('celular_receptor')
        firma_base64 = request.form.get('firma_base64')
        
        # Mantener los valores anteriores si ya existían y no se sube un archivo nuevo
        foto_casa_filename = entrega['foto_casa']
        foto_calle_filename = entrega['foto_calle']
        foto_cargo_filename = entrega['foto_cargo_o_preaviso']
        
        # 1. Captura dinámica de Foto de Casa con validación de extensión
        file_casa = (request.files.get('foto_casa') or 
                     request.files.get('foto_casa_directo') or 
                     request.files.get('foto_casa_preaviso') or 
                     request.files.get('foto_casa_puerta'))
        
        if file_casa and file_casa.filename != '' and allowed_file(file_casa.filename):
            filename_seguro = secure_filename(file_casa.filename)
            foto_casa_filename = f"casa_{entrega_id}_{filename_seguro}"
            file_casa.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_casa_filename))
            
        # 2. Captura dinámica de Foto de Calle con validación de extensión
        file_calle = (request.files.get('foto_calle') or 
                      request.files.get('foto_calle_directo') or 
                      request.files.get('foto_calle_preaviso') or 
                      request.files.get('foto_calle_puerta'))
        
        if file_calle and file_calle.filename != '' and allowed_file(file_calle.filename):
            filename_seguro = secure_filename(file_calle.filename)
            foto_calle_filename = f"calle_{entrega_id}_{filename_seguro}"
            file_calle.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_calle_filename))
            
        # 3. Captura dinámica de Foto de Cargo, Preaviso o Bajo Puerta con validación
        file_cargo = (request.files.get('foto_cargo') or 
                      request.files.get('foto_preaviso') or 
                      request.files.get('foto_cargo_directo') or 
                      request.files.get('foto_cargo_preaviso') or 
                      request.files.get('foto_cargo_puerta'))
        
        if file_cargo and file_cargo.filename != '' and allowed_file(file_cargo.filename):
            filename_seguro = secure_filename(file_cargo.filename)
            prefix = "cargo"
            if tipo_entrega == 'preaviso':
                prefix = "preaviso"
            elif tipo_entrega == 'bajo_puerta':
                prefix = "puerta"
            foto_cargo_filename = f"{prefix}_{entrega_id}_{filename_seguro}"
            file_cargo.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_cargo_filename))
            
        cursor.execute('''
            UPDATE entregas SET
                estado = 'entregado',
                tipo_entrega = ?,
                parentesco = ?,
                nombre_receptor = ?,
                dni_receptor = ?,
                celular_receptor = ?,
                foto_casa = ?,
                foto_calle = ?,
                foto_cargo_o_preaviso = ?,
                firma = ?
            WHERE id = ?
        ''', (
            tipo_entrega, parentesco, nombre_receptor, dni_receptor, celular_receptor,
            foto_casa_filename, foto_calle_filename, foto_cargo_filename, firma_base64, entrega_id
        ))
        conn.commit()
        conn.close()
        
        flash('Entrega registrada exitosamente', 'success')
        return redirect(url_for('motorizado_dashboard'))
        
    conn.close()
    return render_template('motorizado_formulario.html', entrega=entrega, nombre_motorizado=session['nombre'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)