from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import os
import psycopg2
from psycopg2.extras import RealDictCursor

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

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    
    # Si estamos en Render, usará PostgreSQL. Si no hay variable, usará una base local por si haces pruebas en tu PC (opcional)
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    else:
        # Fallback local o manejo si prefieres forzar PostgreSQL
        raise RuntimeError("No se encontró la variable de entorno DATABASE_URL")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla de usuarios (Administradores y Motorizados)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nombre_completo TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    ''')
    
    # Tabla de entregas / documentos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entregas (
            id SERIAL PRIMARY KEY,
            tipo_documento TEXT NOT NULL,
            numero_documento TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            direccion TEXT NOT NULL,
            motorizado_id INTEGER,
            estado TEXT DEFAULT 'pendiente',
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
    
    # Crear admin por defecto si no existe
    cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios (nombre_completo, username, password, rol) VALUES (%s, %s, %s, %s)",
                       ('Administrador General', 'admin', '1234', 'admin'))
        
    conn.commit()
    cursor.close()
    conn.close()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['usuario']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()
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
        
    conn = get_db_connection()
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
    
    cursor.close()
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
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM entregas")
        cursor.execute("DELETE FROM usuarios WHERE username != 'admin'")
        
        conn.commit()
        cursor.close()
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
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO usuarios (nombre_completo, username, password, rol) VALUES (%s, %s, %s, 'motorizado')",
                           (nombre, username, password))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Motorizado creado exitosamente', 'success')
        except psycopg2.errors.UniqueViolation:
            flash('El nombre de usuario ya existe', 'danger')
            
        return redirect(url_for('gestionar_motorizados'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE rol = 'motorizado'")
    motorizados = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('admin_motorizados.html', motorizados=motorizados)

@app.route('/admin/motorizado/eliminar/<int:id>')
def eliminar_motorizado(id):
    if 'rol' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = %s AND rol = 'motorizado'", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Motorizado eliminado', 'success')
    return redirect(url_for('gestionar_motorizados'))

@app.route('/admin/entregas', methods=['GET', 'POST'])
def gestionar_entregas():
    if 'rol' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        tipo_doc = request.form['tipo_documento']
        nro_doc = request.form['numero_documento']
        destinatario = request.form['destinatario']
        direccion = request.form['direccion']
        motorizado_id = request.form['motorizado_id']
        
        cursor.execute('''
            INSERT INTO entregas (tipo_documento, numero_documento, destinatario, direccion, motorizado_id)
            VALUES (%s, %s, %s, %s, %s)
        ''', (tipo_doc, nro_doc, destinatario, direccion, motorizado_id))
        conn.commit()
        cursor.close()
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
    cursor.close()
    conn.close()
    
    return render_template('admin_entregas.html', motorizados=motorizados, entregas=entregas)

@app.route('/admin/entrega/eliminar/<int:id>')
def eliminar_entrega(id):
    if 'rol' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM entregas WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Entrega eliminada correctamente', 'success')
    return redirect(url_for('gestionar_entregas'))

@app.route('/motorizado')
def motorizado_dashboard():
    if 'rol' not in session or session['rol'] != 'motorizado':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM entregas WHERE motorizado_id = %s AND estado = 'pendiente'", (session['user_id'],))
    pendientes = cursor.fetchall()
    
    cursor.execute("SELECT * FROM entregas WHERE motorizado_id = %s AND estado = 'entregado'", (session['user_id'],))
    completadas = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('motorizado_dashboard.html', nombre_motorizado=session['nombre'], pendientes=pendientes, completadas=completadas)

@app.route('/motorizado/detalle/<int:entrega_id>')
def motorizado_detalle(entrega_id):
    if 'rol' not in session or session['rol'] != 'motorizado':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM entregas WHERE id = %s AND motorizado_id = %s AND estado = 'entregado'", (entrega_id, session['user_id']))
    entrega = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not entrega:
        flash('Entrega no encontrada o no autorizada', 'danger')
        return redirect(url_for('motorizado_dashboard'))
        
    return render_template('motorizado_detalle.html', entrega=entrega, nombre_motorizado=session['nombre'])

@app.route('/motorizado/entregar/<int:entrega_id>', methods=['GET', 'POST'])
def registrar_entrega(entrega_id):
    if 'rol' not in session or session['rol'] != 'motorizado':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM entregas WHERE id = %s AND motorizado_id = %s AND estado = 'pendiente'", 
                   (entrega_id, session['user_id']))
    entrega = cursor.fetchone()
    
    if not entrega:
        cursor.close()
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
        
        foto_casa_filename = entrega['foto_casa']
        foto_calle_filename = entrega['foto_calle']
        foto_cargo_filename = entrega['foto_cargo_o_preaviso']
        
        file_casa = (request.files.get('foto_casa') or 
                     request.files.get('foto_casa_directo') or 
                     request.files.get('foto_casa_preaviso') or 
                     request.files.get('foto_casa_puerta'))
        
        if file_casa and file_casa.filename != '' and allowed_file(file_casa.filename):
            filename_seguro = secure_filename(file_casa.filename)
            foto_casa_filename = f"casa_{entrega_id}_{filename_seguro}"
            file_casa.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_casa_filename))
            
        file_calle = (request.files.get('foto_calle') or 
                      request.files.get('foto_calle_directo') or 
                      request.files.get('foto_calle_preaviso') or 
                      request.files.get('foto_calle_puerta'))
        
        if file_calle and file_calle.filename != '' and allowed_file(file_calle.filename):
            filename_seguro = secure_filename(file_calle.filename)
            foto_calle_filename = f"calle_{entrega_id}_{filename_seguro}"
            file_calle.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_calle_filename))
            
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
                tipo_entrega = %s,
                parentesco = %s,
                nombre_receptor = %s,
                dni_receptor = %s,
                celular_receptor = %s,
                foto_casa = %s,
                foto_calle = %s,
                foto_cargo_o_preaviso = %s,
                firma = %s
            WHERE id = %s
        ''', (
            tipo_entrega, parentesco, nombre_receptor, dni_receptor, celular_receptor,
            foto_casa_filename, foto_calle_filename, foto_cargo_filename, firma_base64, entrega_id
        ))
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Entrega registrada exitosamente', 'success')
        return redirect(url_for('motorizado_dashboard'))
        
    cursor.close()
    conn.close()
    return render_template('motorizado_formulario.html', entrega=entrega, nombre_motorizado=session['nombre'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()  # Inicializa la estructura en PostgreSQL al arrancar
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
