from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from datetime import datetime

import os

# Crear carpeta si no existe
os.makedirs("staticc/pedidos", exist_ok=True)

app = Flask(__name__)
app.secret_key = 'una_clave_muy_secreta_123'

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'proyectofinal'
}

def obtener_conexion():
    return mysql.connector.connect(**DB_CONFIG)

# Página principal
@app.route('/')
def index():
    return render_template('index.html')


# Registro de usuarios
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        correo = request.form['correo']
        telefono = request.form['telefono']
        direccion = request.form['direccion']
        rol = 'usuario'

        conexion = obtener_conexion()
        cursor = conexion.cursor()

        try:
            # Insertar en usuarios (si ya existe, se ignora el error)
            cursor.execute(
                'INSERT INTO usuarios (usuario, password, correo, telefono, direccion, rol) '
                'VALUES (%s, %s, %s, %s, %s, %s)', 
                (usuario, password, correo, telefono, direccion, rol)
            )
            conexion.commit()
        except Exception as e:
            # Ignorar error de usuario duplicado
            pass

        # Obtener el ID del usuario recién creado o existente
        cursor.execute("SELECT id FROM usuarios WHERE usuario=%s", (usuario,))
        id_usuario = cursor.fetchone()[0]

        # Insertar en clientes (si ya existe, ignora duplicados)
        try:
            cursor.execute(
                'INSERT INTO clientes (id, nombre, direccion, telefono) VALUES (%s, %s, %s, %s)',
                (id_usuario, usuario, direccion, telefono)
            )
            conexion.commit()
        except Exception as e:
            pass  # Ignora si ya existía

        cursor.close()
        conexion.close()
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/reservar', methods=['POST'])
def reservar():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    # Obtener datos del formulario
    nombre = request.form['name']
    email = request.form['email']
    telefono = request.form['phone']
    tipo = request.form['tipo-solicitud']
    dia = request.form['day']  # Día exacto proporcionado por el usuario (formato YYYY-MM-DD)
    horario = request.form['time']  # Hora exacta proporcionada por el usuario (rango de hora)
    mensaje = request.form['message']
    usuario_id = session['user_id']

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()

        # Insertar la cita en la base de datos
        cursor.execute("""
            INSERT INTO citas (usuario_id, nombre, email, telefono, tipo_solicitud, dia, horario, mensaje, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendiente')
        """, (usuario_id, nombre, email, telefono, tipo, dia, horario, mensaje))

        conn.commit()
        conn.close()

    except Exception as e:
        print("Error al guardar la cita:", e)

    return redirect(url_for('cliente_dashboard'))

@app.route('/admin/citas/aceptar/<int:cita_id>', methods=['POST'])
def aceptar_cita(cita_id):
    hora_final = request.form['hora_final']  # Hora exacta proporcionada por el admin

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE citas
        SET estado='aceptada', hora_final=%s
        WHERE id=%s
    """, (hora_final, cita_id))

    conn.commit()
    conn.close()

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/citas')
def admin_citas():
    if 'usuario' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))

    conn = obtener_conexion()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM citas ORDER BY dia ASC")
    citas = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin_dashboard.html", citas=citas)

@app.route('/admin/citas/rechazar/<int:cita_id>', methods=['POST'])
def rechazar_cita(cita_id):
    conn = obtener_conexion()
    cursor = conn.cursor()

    # Actualizar estado de la cita
    cursor.execute("UPDATE citas SET estado='rechazada' WHERE id=%s", (cita_id,))
    conn.commit()
    conn.close()

    # Redirigir al dashboard principal
    return redirect(url_for('admin_dashboard'))


@app.route('/citas/cancelar/<int:cita_id>')
def cancelar_cita(cita_id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE citas SET estado='cancelada'
        WHERE id=%s AND usuario_id=%s
    """, (cita_id, user_id))

    conn.commit()
    conn.close()

    return redirect(url_for('cliente_dashboard'))




# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute('SELECT * FROM usuarios WHERE usuario=%s AND password=%s', (usuario, password))
        user = cursor.fetchone()
        cursor.close()
        conexion.close()
        if user:
            session['usuario'] = user['usuario']
            session['rol'] = user['rol']
            session['user_id'] = user['id']   # 👈 NECESARIO
            # Redirige según el rol
            if user['rol'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('index'))  # 👈 Redirige al inicio con sesión activa
        else:
            return render_template('login.html', error='Usuario o contraseña incorrectos')
    return render_template('login.html')

# Panel cliente
@app.route('/cliente')
def cliente_dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = obtener_conexion()
    cursor = conn.cursor(dictionary=True)

    # INFO DEL USUARIO
    cursor.execute("SELECT * FROM usuarios WHERE id = %s", (user_id,))
    cliente = cursor.fetchone()

    # CITAS DEL USUARIO
    cursor.execute("SELECT * FROM citas WHERE usuario_id = %s", (user_id,))
    citas = cursor.fetchall()

    # PEDIDOS DEL USUARIO
    cursor.execute("SELECT * FROM pedidos WHERE usuario_id = %s ORDER BY fecha DESC", (user_id,))
    compras = cursor.fetchall()

    # FINANCIAMIENTOS (mensualidades)
    cursor.execute("""
        SELECT f.*, a.marca, a.modelo, a.precio
        FROM financiamientos f
        INNER JOIN autos a ON f.auto_id = a.id
        WHERE f.usuario_id = %s
        ORDER BY f.fecha DESC
    """, (user_id,))
    pagos = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'cliente_dashboard.html',
        cliente=cliente,
        citas=citas,
        compras=compras,
        pagos=pagos
    )


# Página de empresa
@app.route('/empresa')
def empresa():
    return render_template('empresa.html')

# Cierre de sesión
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/autos')
def autos():
    # 🔐 Si NO está logueado, lo manda al login
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("SELECT * FROM autos")
    autos = cursor.fetchall()

    cursor.close()
    conexion.close()

    categorias = {
        'Nuevo': [a for a in autos if a['categoria'] == 'nuevo'],
        'Seminuevo': [a for a in autos if a['categoria'] == 'seminuevo'],
        'SUVs y Camionetas': [a for a in autos if a['categoria'] in ['suv', 'camioneta']],
        'Híbridos y Eléctricos': [a for a in autos if a['categoria'] in ['hibrido', 'electrico']],
        'Deportivos': [a for a in autos if a['categoria'] == 'deportivo']
    }

    return render_template('autos.html', categorias=categorias)


@app.route('/agregar_auto', methods=['POST'])
def agregar_auto():
    if 'usuario' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))

    # Obtener datos del formulario
    marca = request.form['marca']
    modelo = request.form['modelo']
    anio = request.form['anio']
    precio = request.form['precio']
    kilometraje = request.form.get('kilometraje', None)
    motor = request.form.get('motor', '')
    traccion = request.form.get('traccion', '')
    color = request.form.get('color', '')
    categoria = request.form['categoria']
    imagen = request.form.get('imagen', '')

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO autos (marca, modelo, año, precio, kilometraje, motor, traccion, color, categoria, imagen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (marca, modelo, anio, precio, kilometraje, motor, traccion, color, categoria, imagen))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        print("Error al agregar auto:", e)
        return "Error al agregar auto", 500

@app.route('/administrar_autos', methods=['POST'])
def administrar_autos():
    if 'usuario' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))

    # Obtener datos del formulario
    auto_id = request.form['id']
    marca = request.form['marca']
    modelo = request.form['modelo']
    anio = request.form['anio']
    precio = request.form['precio']
    kilometraje = request.form.get('kilometraje', None)
    motor = request.form.get('motor', '')
    traccion = request.form.get('traccion', '')
    color = request.form.get('color', '')
    categoria = request.form['categoria']
    imagen = request.form.get('imagen', '')

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE autos
            SET marca=%s, modelo=%s, año=%s, precio=%s, kilometraje=%s,
                motor=%s, traccion=%s, color=%s, categoria=%s, imagen=%s
            WHERE id=%s
        """, (marca, modelo, anio, precio, kilometraje, motor, traccion, color, categoria, imagen, auto_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        print("Error al actualizar auto:", e)
        return "Error al actualizar auto", 500

@app.route('/admin')
def admin_dashboard():
    if 'usuario' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))

    conn = obtener_conexion()
    cursor = conn.cursor(dictionary=True)

    # Traer todos los usuarios
    cursor.execute('SELECT * FROM usuarios')
    usuarios = cursor.fetchall()

    # Traer autos
    cursor.execute('SELECT * FROM autos')
    autos = cursor.fetchall()

    # Traer citas
    cursor.execute('SELECT * FROM citas ORDER BY dia ASC')
    citas = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_dashboard.html',
                           usuario=session['usuario'],
                           usuarios=usuarios,
                           autos=autos,
                           citas=citas)


@app.route('/autos/eliminar', methods=['POST'])
def eliminar_auto():
    if 'usuario' not in session or session['rol'] != 'admin':
        return redirect(url_for('login'))

    auto_id = request.form['id']  # Se enviará desde el formulario/botón

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM autos WHERE id=%s", (auto_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        print("Error al eliminar auto:", e)
        return "Error al eliminar auto", 500


@app.route('/agregar_carrito', methods=['POST'])
def agregar_carrito():
    auto_id = request.json.get('id')

    if 'carrito' not in session:
        session['carrito'] = []

    if auto_id not in session['carrito']:
        session['carrito'].append(auto_id)
        session.modified = True

    return jsonify({"ok": True, "total": len(session['carrito'])})

@app.route('/carrito')
def carrito():
    carrito_ids = session.get('carrito', [])

    if not carrito_ids:
        autos = []
    else:
        conn = obtener_conexion()
        cursor = conn.cursor(dictionary=True)
        formato = ",".join(["%s"] * len(carrito_ids))
        cursor.execute(f"SELECT * FROM autos WHERE id IN ({formato})", carrito_ids)
        autos = cursor.fetchall()
        cursor.close()
        conn.close()

    return render_template("carrito.html", autos=autos)

@app.route('/carrito/eliminar', methods=['POST'])
def carrito_eliminar():
    auto_id = int(request.form['id'])

    if 'carrito' in session:
        if auto_id in session['carrito']:
            session['carrito'].remove(auto_id)
            session.modified = True

    return redirect(url_for('carrito'))

@app.route('/checkout')
def checkout():
    carrito_ids = session.get('carrito', [])

    if not carrito_ids:
        return redirect(url_for('carrito'))

    conn = obtener_conexion()
    cursor = conn.cursor(dictionary=True)
    formato = ",".join(["%s"] * len(carrito_ids))
    cursor.execute(f"SELECT * FROM autos WHERE id IN ({formato})", carrito_ids)
    autos = cursor.fetchall()

    cursor.close()
    conn.close()

    total = float(sum(float(a["precio"]) for a in autos))

    return render_template("checkout.html", autos=autos, total=total)

@app.route('/checkout/finalizar', methods=['POST'])
def finalizar_pago():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    usuario = session['usuario']
    usuario_id = session.get('user_id')

    carrito_ids = session.get('carrito', [])
    if not carrito_ids:
        return redirect(url_for('carrito'))

    # Obtener meses elegidos
    meses = int(request.form['meses'])

    # Obtener autos del carrito
    conn = obtener_conexion()
    cursor = conn.cursor(dictionary=True)
    formato = ",".join(["%s"] * len(carrito_ids))
    cursor.execute(f"SELECT * FROM autos WHERE id IN ({formato})", carrito_ids)
    autos = cursor.fetchall()

    total = float(sum(float(a["precio"]) for a in autos))
    enganche = total * 0.50
    saldo_financiar = total - enganche
    mensualidad = saldo_financiar / meses

    # Guardar pedido
    cursor2 = conn.cursor()
    cursor2.execute("INSERT INTO pedidos (usuario_id, total) VALUES (%s, %s)", (usuario_id, total))
    pedido_id = cursor2.lastrowid

    for auto in autos:
        # Items del pedido
        cursor2.execute(
            "INSERT INTO pedido_items (pedido_id, auto_id, precio) VALUES (%s, %s, %s)",
            (pedido_id, auto["id"], auto["precio"])
        )
        # Financiamiento
        cursor2.execute(
            "INSERT INTO financiamientos (usuario_id, auto_id, enganche, meses, mensualidad) VALUES (%s, %s, %s, %s, %s)",
            (usuario_id, auto["id"], enganche, meses, mensualidad)
        )

    conn.commit()
    cursor.close()
    cursor2.close()
    conn.close()

    # Crear PDF
    os.makedirs("staticc/pedidos", exist_ok=True)
    filename = f"pedido_{pedido_id}.pdf"
    ruta_pdf = os.path.join("staticc/pedidos", filename)

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from datetime import datetime

    c = canvas.Canvas(ruta_pdf, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 750, "Comprobante de Pedido")
    c.setFont("Helvetica", 12)
    c.drawString(40, 730, f"Pedido ID: {pedido_id}")
    c.drawString(40, 710, f"Cliente: {usuario}")
    c.drawString(40, 690, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    c.drawString(40, 660, "Autos Comprados:")
    y = 640
    for auto in autos:
        c.drawString(50, y, f"- {auto['marca']} {auto['modelo']} | ${auto['precio']:,.2f}")
        y -= 20

    c.drawString(40, y-10, f"Enganche (50%): ${enganche:,.2f}")
    c.drawString(40, y-30, f"Meses: {meses}")
    c.drawString(40, y-50, f"Mensualidad: ${mensualidad:,.2f}")
    c.save()

    # Vaciar carrito
    session['carrito'] = []

    return render_template("compra_exitosa.html",
                           pedido_id=pedido_id,
                           pdf=filename,
                           autos=autos,
                           meses=meses,
                           enganche=enganche,
                           mensualidad=mensualidad)

@app.route('/editar_perfil', methods=['GET', 'POST'])
def editar_perfil():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    usuario_sesion = session['usuario']

    conn = obtener_conexion()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # Obtener los nuevos datos del formulario
        nuevo_usuario = request.form['usuario']
        correo = request.form['correo']
        telefono = request.form['telefono']
        direccion = request.form['direccion']

        # Actualizar la base de datos con los nuevos valores
        cursor.execute("""
            UPDATE usuarios
            SET usuario=%s, correo=%s, telefono=%s, direccion=%s
            WHERE usuario=%s
        """, (nuevo_usuario, correo, telefono, direccion, usuario_sesion))

        conn.commit()

        # Actualiza el nombre de usuario en la sesión
        session['usuario'] = nuevo_usuario

        cursor.close()
        conn.close()

        # Redirige al dashboard del cliente
        return redirect(url_for('cliente_dashboard'))

    # GET → Mostrar los datos del usuario
    cursor.execute("SELECT * FROM usuarios WHERE usuario=%s", (usuario_sesion,))
    cliente = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("editar_perfil.html", cliente=cliente)


@app.route('/pagar_mensualidad/<int:fin_id>', methods=['POST'])
def pagar_mensualidad(fin_id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = obtener_conexion()
    cursor = conn.cursor(dictionary=True)

    # obtener datos
    cursor.execute("SELECT * FROM financiamientos WHERE id = %s", (fin_id,))
    fin = cursor.fetchone()

    if not fin:
        return redirect(url_for('cliente_dashboard'))

    # sumar un pago
    nuevos_pagados = fin['pagados'] + 1

    cursor.execute("UPDATE financiamientos SET pagados = %s WHERE id = %s",
                   (nuevos_pagados, fin_id))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('cliente_dashboard'))


#jjjjj

@app.route('/pago', methods=['POST'])
def pago():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    # Obtener datos del checkout
    meses = int(request.form['meses'])
    autos_ids = request.form.getlist('autos_ids')

    if not autos_ids:
        return redirect(url_for('carrito'))

    # Obtener información de los autos
    conn = obtener_conexion()
    cursor = conn.cursor(dictionary=True)
    formato = ",".join(["%s"] * len(autos_ids))
    cursor.execute(f"SELECT * FROM autos WHERE id IN ({formato})", autos_ids)
    autos = cursor.fetchall()
    cursor.close()
    conn.close()

    # Calcular total y enganche
    total = sum(float(a['precio']) for a in autos)
    enganche = total * 0.50
    saldo_financiar = total - enganche
    mensualidad = saldo_financiar / meses

    return render_template(
        'pago_tarjeta.html',
        autos=autos,
        meses=meses,
        total=total,
        enganche=enganche,
        mensualidad=mensualidad
    )



# BUSCAR USUARIO
@app.route('/admin/usuarios/buscar/<int:id>')
def buscar_usuario(id):
    if 'usuario' not in session or session['rol'] != 'admin':
        return jsonify({'error': 'No autorizado'}), 403

    conn = obtener_conexion()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE id=%s", (id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        return jsonify({'error': 'Usuario no encontrado'})
    
    return jsonify({
        'usuario': user['usuario'],
        'direccion': user.get('direccion', ''),
        'telefono': user.get('telefono', '')
    })


# MODIFICAR USUARIO
@app.route('/admin/usuarios/modificar/<int:id>', methods=['POST'])
def modificar_usuario(id):
    if 'usuario' not in session or session['rol'] != 'admin':
        return jsonify({'error': 'No autorizado'}), 403

    data = request.get_json()  # ⚠️ Importante
    nombre = data.get('nombre')
    direccion = data.get('direccion', '')
    telefono = data.get('telefono', '')

    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE usuarios
        SET usuario=%s, direccion=%s, telefono=%s
        WHERE id=%s
    """, (nombre, direccion, telefono, id))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'ok': True})

# Eliminar usuario
@app.route('/admin/usuarios/eliminar/<int:user_id>', methods=['POST'])
def eliminar_usuario(user_id):
    if 'usuario' not in session or session['rol'] != 'admin':
        return jsonify({'error': 'No autorizado'}), 403

    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id=%s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'ok': True})

# Guardar nuevo usuario
@app.route('/admin/usuarios/guardar', methods=['POST'])
def guardar_usuario():
    if 'usuario' not in session or session['rol'] != 'admin':
        return jsonify({'error': 'No autorizado'}), 403

    data = request.json
    nombre = data.get('nombre')
    direccion = data.get('direccion')
    telefono = data.get('telefono')
    password = data.get('password', '1234')  # Puedes poner un valor por defecto o pedirlo

    if not nombre:
        return jsonify({'error': 'El nombre es obligatorio'}), 400

    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO usuarios (usuario, password, direccion, telefono, rol)
        VALUES (%s, %s, %s, %s, 'usuario')
    """, (nombre, password, direccion, telefono))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'ok': True})




# Ejecutar servidor
if __name__ == '__main__':
    app.run(debug=True)