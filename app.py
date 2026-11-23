"""Intercambio secreto: aplicación Streamlit para familias.

Correr: streamlit run app.py
"""
from __future__ import annotations

from collections import Counter
from email.message import EmailMessage
import hashlib
from io import BytesIO
import smtplib
import ssl

import pandas as pd
import streamlit as st

from sorteo import Participante, sortear, validar_participantes


st.set_page_config(page_title="Intercambio secreto", page_icon="🎁", layout="wide")

COLUMNAS = ["familia", "nombre", "correo"]


def tabla_vacia() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="str") for c in COLUMNAS})


def importar_excel_o_csv(contenido: bytes, nombre: str) -> pd.DataFrame:
    if nombre.lower().endswith(".csv"):
        df = pd.read_csv(BytesIO(contenido), sep=None, engine="python", dtype=str)
    else:
        df = pd.read_excel(BytesIO(contenido), sheet_name=0, dtype=str)
    nombres = {
        "familia": "familia", "grupo": "familia", "apellido": "familia", "apellidos": "familia",
        "nombre": "nombre", "integrante": "nombre", "participante": "nombre",
        "correo": "correo", "email": "correo", "e-mail": "correo", "correo electronico": "correo",
        "correo electrónico": "correo",
    }
    df.columns = [nombres.get(str(c).strip().casefold(), str(c).strip().casefold()) for c in df.columns]
    faltantes = set(COLUMNAS) - set(df.columns)
    if faltantes:
        raise ValueError("Faltan las columnas: " + ", ".join(sorted(faltantes)))
    return df[COLUMNAS].fillna("").astype(str)


def crear_mensaje(
    emisor: Participante,
    destinatario: Participante,
    remitente: str,
    titulo: str,
    presupuesto: int,
    fecha: str,
    notas: str,
) -> EmailMessage:
    mensaje = EmailMessage()
    mensaje["From"] = remitente.strip()
    mensaje["To"] = emisor.correo
    mensaje["Subject"] = f"🎁 Tu asignación privada: {titulo}"
    partes = [
        f"¡Hola, {emisor.nombre}!",
        "",
        f"Ya se realizó el sorteo de «{titulo}».",
        "",
        f"🎁 Te toca regalarle a: {destinatario.nombre}",
        f"Familia de tu destinatario: {destinatario.familia}",
        "",
        "Esta asignación es PERSONAL y CONFIDENCIAL. No compartas este correo.",
    ]
    if presupuesto > 0:
        partes.extend(["", f"Presupuesto sugerido: ${presupuesto:,.0f} MXN"])
    if fecha.strip():
        partes.append(f"Fecha de entrega: {fecha.strip()}")
    if notas.strip():
        partes.extend(["", "Indicaciones del organizador:", notas.strip()])
    partes.extend(["", "¡Que disfruten el intercambio!"])
    mensaje.set_content("\n".join(partes))
    return mensaje


def abrir_smtp(host: str, puerto: int, modo: str, usuario: str, clave: str):
    contexto = ssl.create_default_context()
    if modo == "SSL/TLS (465)":
        conexion = smtplib.SMTP_SSL(host=host.strip(), port=puerto, context=contexto, timeout=20)
    else:
        conexion = smtplib.SMTP(host=host.strip(), port=puerto, timeout=20)
        conexion.ehlo()
        conexion.starttls(context=contexto)
        conexion.ehlo()
    try:
        conexion.login(usuario.strip(), clave)
    except Exception:
        conexion.quit()
        raise
    return conexion


def enviar_pendientes(
    host: str, puerto: int, modo: str, usuario: str, clave: str, remitente: str
) -> tuple[int, str | None]:
    # Los emparejamientos únicamente se guardan en la sesión activa hasta
    # que el servidor SMTP acepta todos los mensajes.
    operativo = st.session_state["sorteo_pendiente"]
    personas = operativo["personas"]
    asignaciones = operativo["asignaciones"]
    enviados = operativo["enviados"]
    pendientes = [i for i in range(len(personas)) if i not in enviados]
    barra = st.progress(len(enviados) / len(personas))
    estado = st.empty()
    conexion = None
    error = None
    try:
        conexion = abrir_smtp(host, puerto, modo, usuario, clave)
        for i in pendientes:
            mensaje = crear_mensaje(
                emisor=personas[i],
                destinatario=personas[asignaciones[i]],
                remitente=remitente,
                titulo=operativo["titulo"],
                presupuesto=operativo["presupuesto"],
                fecha=operativo["fecha"],
                notas=operativo["notas"],
            )
            # En caso de fallo de una dirección, avanzamos con las demás.
            try:
                conexion.send_message(mensaje)
                enviados.add(i)
            except smtplib.SMTPException:
                continue
            barra.progress(len(enviados) / len(personas))
            estado.write(f"Notificaciones aceptadas por SMTP: {len(enviados)} / {len(personas)}")
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        # No mostrar direcciones o contenidos del mensaje en errores de interfaz.
        error = f"No se pudo completar el envío ({type(exc).__name__}). Revisa el servidor o las credenciales."
    finally:
        if conexion is not None:
            try:
                conexion.quit()
            except (OSError, smtplib.SMTPException):
                pass

    cuenta = len(enviados)
    if cuenta == len(personas):
        # Borrado de resultados de la sesión una vez aceptados todos los correos.
        st.session_state["evento_terminado"] = {
            "participantes": len(personas),
            "familias": len({p.familia.casefold() for p in personas}),
            "notificaciones": cuenta,
        }
        del st.session_state["sorteo_pendiente"]
        st.session_state["bloqueado"] = True
    return cuenta, error


if "personas_df" not in st.session_state:
    st.session_state["personas_df"] = tabla_vacia()
if "editor_version" not in st.session_state:
    st.session_state["editor_version"] = 0
if "bloqueado" not in st.session_state:
    st.session_state["bloqueado"] = False

st.title("🎁 Intercambio secreto de regalos")
st.write(
    "Registra participantes por familia, realiza un sorteo sin coincidencias familiares "
    "y envía cada asignación por correo **sin mostrar el resultado al organizador**."
)

st.info(
    "**Privacidad:** no se imprimen ni se guardan emparejamientos en archivos o bases de datos. "
    "El administrador no los ve en esta interfaz. Quien controle el servidor o la cuenta "
    "de correo podría acceder a ellos; esto no es un protocolo criptográfico contra administradores maliciosos.",
    icon="🔒",
)

with st.sidebar:
    st.header("✉️ Configuración de correo")
    st.caption("Se usa SMTP para notificar a cada persona directamente. Credenciales solo en esta sesión.")
    host = st.text_input("Servidor SMTP", value="smtp.gmail.com")
    modo = st.selectbox("Seguridad", ["STARTTLS (587)", "SSL/TLS (465)"])
    puerto = st.number_input("Puerto", min_value=1, max_value=65535, value=587 if modo.startswith("STARTTLS") else 465)
    usuario = st.text_input("Usuario SMTP (correo remitente)", placeholder="organizador@ejemplo.com")
    clave = st.text_input("Contraseña SMTP o contraseña de aplicación", type="password")
    remitente = st.text_input("Correo remitente", value=usuario)
    st.caption(
        "Con Gmail normalmente necesitas verificación en dos pasos y una contraseña de aplicación, "
        "si tu cuenta permite ese método. Importante: algunos servicios guardan mensajes en «Enviados»."
    )

st.subheader("1. Participantes")
st.caption("Columnas obligatorias: **familia**, **nombre** y **correo**. Usa el mismo nombre de familia en todas sus filas.")
archivo = st.file_uploader("Importar una hoja de Excel (.xlsx) o CSV", type=["xlsx", "csv"], disabled=st.session_state["bloqueado"] or "sorteo_pendiente" in st.session_state)
if archivo is not None and not st.session_state["bloqueado"] and "sorteo_pendiente" not in st.session_state:
    contenido = archivo.getvalue()
    identificador = hashlib.sha256(contenido).hexdigest()
    if st.session_state.get("hash_importado") != identificador:
        try:
            st.session_state["personas_df"] = importar_excel_o_csv(contenido, archivo.name)
            st.session_state["editor_version"] += 1
            st.session_state["hash_importado"] = identificador
            st.success("Archivo cargado. Puedes corregir la tabla antes de hacer el sorteo.")
        except Exception as exc:
            st.error(f"No se pudo importar el archivo: {exc}")

bloqueado = st.session_state["bloqueado"] or "sorteo_pendiente" in st.session_state
edicion = st.data_editor(
    st.session_state["personas_df"],
    num_rows="dynamic", hide_index=True, use_container_width=True,
    disabled=bloqueado,
    key=f"editor_{st.session_state['editor_version']}",
    column_config={
        "familia": st.column_config.TextColumn("Familia o apellidos", required=True),
        "nombre": st.column_config.TextColumn("Nombre del integrante", required=True),
        "correo": st.column_config.TextColumn("Correo privado", required=True),
    },
)
if not bloqueado:
    st.session_state["personas_df"] = edicion.copy()

filas = st.session_state["personas_df"].fillna("").to_dict(orient="records")
personas, errores = validar_participantes(filas)
conteo = Counter(p.familia.casefold() for p in personas)

col_a, col_b, col_c = st.columns(3)
col_a.metric("Participantes", len(personas))
col_b.metric("Familias", len(conteo))
col_c.metric("Familia más grande", max(conteo.values(), default=0))

if errores and not bloqueado:
    for e in errores:
        st.warning(e)
elif not errores and not bloqueado:
    st.success("Lista válida. Es posible asignar un destinatario diferente a cada participante.")

if not bloqueado:
    if st.button("Borrar participantes", type="secondary"):
        st.session_state["personas_df"] = tabla_vacia()
        st.session_state["hash_importado"] = None
        st.session_state["editor_version"] += 1
        st.rerun()

st.subheader("2. Detalles del intercambio")
titulo = st.text_input("Nombre del evento", value="Intercambio familiar 2026", disabled=bloqueado)
presupuesto = st.number_input("Presupuesto sugerido (MXN; 0 = sin límite especificado)", min_value=0, max_value=1000000, value=500, step=50, disabled=bloqueado)
fecha = st.text_input("Fecha de entrega (opcional)", placeholder="24 de diciembre de 2026", disabled=bloqueado)
notas = st.text_area("Reglas o indicaciones extra (opcional)", disabled=bloqueado)

st.subheader("3. Sorteo y notificaciones")
st.write(
    "El sorteo garantiza **un regalo entregado y uno recibido por persona**, con destinatarios "
    "de otras familias. Los emparejamientos no se pueden consultar desde el panel del administrador."
)

config_ok = bool(host.strip() and usuario.strip() and clave and remitente.strip())
if not bloqueado:
    if st.button("🎲 Sortear y enviar correos privados", type="primary", disabled=bool(errores) or not config_ok):
        asignaciones = sortear(personas)
        st.session_state["sorteo_pendiente"] = {
            "personas": personas,
            "asignaciones": asignaciones,
            "enviados": set(),
            "titulo": titulo,
            "presupuesto": int(presupuesto),
            "fecha": fecha,
            "notas": notas,
        }
        cuenta, error = enviar_pendientes(host, int(puerto), modo, usuario, clave, remitente)
        if error:
            st.error(error)
        if "sorteo_pendiente" in st.session_state:
            st.warning(f"Se aceptaron {cuenta} de {len(personas)} correos. No vuelvas a sortear: reintenta solo los pendientes.")
        else:
            st.success(f"Sorteo finalizado: {cuenta} correos aceptados por el servidor de correo.")
elif "sorteo_pendiente" in st.session_state:
    pendientes = st.session_state["sorteo_pendiente"]
    st.warning(
        f"Sorteo ya creado: {len(pendientes['enviados'])} / {len(pendientes['personas'])} "
        "correos aceptados por SMTP. No modifiques participantes ni reinicies la sesión."
    )
    if st.button("↻ Reintentar solo correos pendientes", type="primary", disabled=not config_ok):
        cuenta, error = enviar_pendientes(host, int(puerto), modo, usuario, clave, remitente)
        if error:
            st.error(error)
        if "sorteo_pendiente" in st.session_state:
            st.warning(f"Siguen pendientes {len(pendientes['personas']) - cuenta} notificaciones. Revisa SMTP y vuelve a reintentar.")
        else:
            st.success(f"Sorteo finalizado: {cuenta} correos aceptados por SMTP.")
elif st.session_state["bloqueado"]:
    resumen = st.session_state["evento_terminado"]
    st.success(
        f"Sorteo finalizado: {resumen['participantes']} participantes, "
        f"{resumen['familias']} familias y "
        f"{resumen['notificaciones']} mensajes aceptados por el servidor SMTP."
    )
    st.caption("Los emparejamientos ya no se encuentran en la sesión de la aplicación. No se muestran al administrador.")
else:
    st.caption("Completa los participantes y la configuración SMTP para habilitar el sorteo.")

st.divider()
st.caption(
    "Aceptado por SMTP no significa recibido o leído. La recepción depende del proveedor y de la "
    "dirección de cada participante. No es posible recuperar el mismo sorteo si se pierde la sesión antes de terminar."
)
