
import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
from io import BytesIO

DB = "inventario_obra.db"

def db():
    return sqlite3.connect(DB)

def init_db():
    con = db()
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS empresa (
        id INTEGER PRIMARY KEY CHECK (id=1),
        razon_social TEXT DEFAULT 'J&G INARQ',
        nit TEXT DEFAULT '',
        telefono TEXT DEFAULT '',
        email TEXT DEFAULT '',
        direccion TEXT DEFAULT ''
    )""")
    cur.execute("INSERT OR IGNORE INTO empresa (id) VALUES (1)")
    cur.execute("""CREATE TABLE IF NOT EXISTS inventario (
        codigo TEXT PRIMARY KEY,
        categoria TEXT, elemento TEXT, unidad TEXT,
        stock_inicial REAL DEFAULT 0, entradas REAL DEFAULT 0,
        salidas REAL DEFAULT 0, stock_actual REAL DEFAULT 0,
        stock_minimo REAL DEFAULT 0, ubicacion TEXT,
        responsable TEXT, observaciones TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT, codigo TEXT, elemento TEXT, tipo TEXT,
        cantidad REAL, responsable TEXT, destino_origen TEXT,
        observaciones TEXT
    )""")
    con.commit()
    con.close()

def empresa():
    con = db()
    df = pd.read_sql_query("SELECT * FROM empresa WHERE id=1", con)
    con.close()
    return df.iloc[0].to_dict()

def inventario():
    con = db()
    df = pd.read_sql_query("SELECT * FROM inventario ORDER BY codigo", con)
    con.close()
    return df

def movimientos():
    con = db()
    df = pd.read_sql_query("SELECT * FROM movimientos ORDER BY id DESC", con)
    con.close()
    return df

init_db()
emp = empresa()
st.set_page_config(page_title="Inventario de Obra", page_icon="🏗️", layout="wide")

# Encabezado
st.sidebar.markdown(f"## 🏗️ {emp['razon_social']}")
st.sidebar.caption("Sistema de Inventario de Obra")
menu = st.sidebar.radio("Módulo", [
    "Dashboard", "Inventario", "Movimientos", "Configuración"
])

if menu == "Dashboard":
    inv = inventario()
    mov = movimientos()

    st.title("Inventario de Obra")
    st.caption(f"{emp['razon_social']}  •  Control de materiales, herramientas, equipos y EPP")

    total = len(inv)
    stock = inv["stock_actual"].sum() if not inv.empty else 0
    bajos = int((inv["stock_actual"] <= inv["stock_minimo"]).sum()) if not inv.empty else 0
    sin_stock = int((inv["stock_actual"] <= 0).sum()) if not inv.empty else 0

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total de ítems", total)
    c2.metric("En stock", int(stock))
    c3.metric("Stock bajo", bajos)
    c4.metric("Sin stock", sin_stock)

    st.divider()

    a,b = st.columns([1,1])
    with a:
        st.subheader("Alertas de stock mínimo")
        if not inv.empty:
            alertas = inv[inv["stock_actual"] <= inv["stock_minimo"]]
            st.dataframe(
                alertas[["codigo","elemento","stock_actual","stock_minimo","ubicacion"]],
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No hay elementos registrados.")
    with b:
        st.subheader("Últimos movimientos")
        st.dataframe(
            mov.head(8)[["fecha","elemento","tipo","cantidad","responsable","destino_origen"]],
            use_container_width=True, hide_index=True
        )

elif menu == "Inventario":
    st.title("📦 Inventario")

    with st.expander("➕ Nuevo elemento"):
        with st.form("nuevo"):
            c1,c2,c3 = st.columns(3)
            codigo = c1.text_input("Código *")
            elemento = c2.text_input("Elemento *")
            categoria = c3.selectbox("Categoría", ["Materiales","Herramientas","Equipos","EPP","Otros"])
            c1,c2,c3 = st.columns(3)
            unidad = c1.text_input("Unidad", "Unidad")
            inicial = c2.number_input("Stock inicial", min_value=0.0, step=1.0)
            minimo = c3.number_input("Stock mínimo", min_value=0.0, step=1.0)
            c1,c2 = st.columns(2)
            ubicacion = c1.text_input("Ubicación", "Bodega")
            responsable = c2.text_input("Responsable")
            observaciones = st.text_area("Observaciones")
            ok = st.form_submit_button("Guardar elemento", type="primary")

            if ok:
                con = db()
                try:
                    con.execute("""INSERT INTO inventario
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (codigo,categoria,elemento,unidad,inicial,0,0,inicial,minimo,
                     ubicacion,responsable,observaciones))
                    con.commit()
                    st.success("Elemento guardado.")
                except sqlite3.IntegrityError:
                    st.error("Ese código ya existe.")
                finally:
                    con.close()

    inv = inventario()
    if not inv.empty:
        st.dataframe(inv, use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay elementos.")

elif menu == "Movimientos":
    st.title("🔄 Entradas y salidas")
    inv = inventario()

    if inv.empty:
        st.warning("Primero registra elementos en Inventario.")
    else:
        with st.form("mov"):
            c1,c2,c3 = st.columns(3)
            fecha = c1.date_input("Fecha", date.today())
            codigo = c2.selectbox("Código", inv["codigo"].tolist())
            tipo = c3.selectbox("Tipo", ["Entrada","Salida"])

            item = inv[inv.codigo == codigo].iloc[0]
            st.info(f"**{item.elemento}** — Stock actual: **{item.stock_actual} {item.unidad}**")

            c1,c2,c3 = st.columns(3)
            cantidad = c1.number_input("Cantidad", min_value=0.01, step=1.0)
            responsable = c2.text_input("Responsable")
            destino = c3.text_input("Destino / Origen")
            observaciones = st.text_area("Observaciones")
            ok = st.form_submit_button("Registrar movimiento", type="primary")

            if ok:
                stock = float(item.stock_actual)
                if tipo == "Salida" and cantidad > stock:
                    st.error("La cantidad de salida supera el stock disponible.")
                else:
                    con = db()
                    if tipo == "Entrada":
                        con.execute("""UPDATE inventario SET entradas=entradas+?,
                        stock_actual=stock_actual+? WHERE codigo=?""",
                        (cantidad,cantidad,codigo))
                    else:
                        con.execute("""UPDATE inventario SET salidas=salidas+?,
                        stock_actual=stock_actual-? WHERE codigo=?""",
                        (cantidad,cantidad,codigo))
                    con.execute("""INSERT INTO movimientos
                    (fecha,codigo,elemento,tipo,cantidad,responsable,destino_origen,observaciones)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (str(fecha),codigo,item.elemento,tipo,cantidad,responsable,destino,observaciones))
                    con.commit()
                    con.close()
                    st.success("Movimiento registrado.")

        st.subheader("Historial")
        st.dataframe(movimientos(), use_container_width=True, hide_index=True)

else:
    st.title("⚙️ Configuración de empresa")
    st.caption("Aquí puedes cambiar la razón social que aparece en todo el sistema.")

    with st.form("empresa"):
        razon = st.text_input("Razón social *", emp["razon_social"])
        nit = st.text_input("NIT", emp["nit"])
        telefono = st.text_input("Teléfono", emp["telefono"])
        email = st.text_input("Correo electrónico", emp["email"])
        direccion = st.text_input("Dirección", emp["direccion"])

        guardar = st.form_submit_button("💾 Guardar configuración", type="primary")

        if guardar:
            con = db()
            con.execute("""UPDATE empresa SET razon_social=?, nit=?, telefono=?,
            email=?, direccion=? WHERE id=1""",
            (razon,nit,telefono,email,direccion))
            con.commit()
            con.close()
            st.success("Configuración guardada. Recarga la página para actualizar el encabezado.")

    st.divider()
    st.subheader("Datos actuales")
    st.write(f"**Razón social:** {emp['razon_social']}")
    st.write(f"**NIT:** {emp['nit']}")
    st.write(f"**Teléfono:** {emp['telefono']}")
    st.write(f"**Correo:** {emp['email']}")
    st.write(f"**Dirección:** {emp['direccion']}")

st.sidebar.divider()
st.sidebar.caption("© 2026 • Sistema de Inventario de Obra")
