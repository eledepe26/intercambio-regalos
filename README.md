# Intercambio secreto de regalos 🎁

Aplicación en Python + Streamlit para sortear entre familias. Cada participante regala a **una persona de otra familia**, y cada persona recibe **exactamente un regalo**. La interfaz del organizador **no muestra las asignaciones**.

## Archivos

- `app.py`: aplicación con captura manual, importación y notificaciones privadas SMTP.
- `sorteo.py`: algoritmo de emparejamiento y comprobación de restricciones.
- `plantilla_familias.xlsx`: ejemplo editable con `familia`, `nombre`, `correo`.
- `test_sorteo.py`: pruebas del algoritmo.
- `requirements.txt`: paquetes Python.

## Cómo iniciar en Windows

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Si ya tienes instaladas las dependencias, basta con `py -m streamlit run app.py`.

Abre la URL local que indique Streamlit (normalmente `http://localhost:8501`). Solo el organizador necesita acceder a la aplicación; los participantes reciben la asignación por correo electrónico.

## Funcionamiento

1. Introduce a cada persona en una fila o importa el Excel. Si utilizas Google Sheets, elige **Archivo → Descargar → Microsoft Excel (.xlsx)** y sube el archivo resultante.
2. Utiliza nombres consistentes de familia (`García`, `López`...). Cada correo debe corresponder a una persona distinta.
3. Elige un nombre de evento, presupuesto y fecha de entrega opcional.
4. Configura el servidor SMTP y las credenciales. Para Gmail, generalmente `smtp.gmail.com`, `587`, `STARTTLS`; necesitarás una contraseña de aplicación cuando esté disponible para tu cuenta. Otros proveedores tienen sus propias instrucciones.
5. Presiona **Sortear y enviar correos privados**. No se muestran los destinatarios en la interfaz.
6. Si falla un envío, no se realiza otro sorteo: el botón **Reintentar solo correos pendientes** conserva las mismas parejas dentro de esa sesión.

**Importante:** Los correos de la plantilla usan `example.com` y son ficticios. Sustitúyelos por correos reales antes de enviar. Verifica primero el remitente y el consentimiento de los participantes para recibir el correo.

## Restricción matemática

El programa comprueba que la familia más numerosa no tenga más de la mitad de los participantes. Si esa condición se cumple y hay al menos dos familias, existe una asignación completa con estas reglas. No hay necesidad de realizar sorteos repetidos hasta acertar: se usa un algoritmo de emparejamiento bipartito con caminos aumentantes y aleatorización criptográfica.

## Qué significa «privado» en esta versión

- El administrador **no ve las parejas en la interfaz**.
- El programa **no imprime las parejas ni las exporta a un archivo de resultados**.
- Las asignaciones permanecen **temporalmente en la memoria de la sesión** durante el envío, por si hay que reintentar mensajes fallidos. Cuando el servidor SMTP ha aceptado todos los mensajes, se eliminan de esa sesión.
- Si se cierra o reinicia la sesión antes de completar los envíos, **no se puede reanudar el mismo sorteo**. No hagas un segundo sorteo si ya recibieron correos algunos integrantes.
- Algunos servicios de correo registran el mensaje enviado en «Enviados». Si el organizador es dueño de esa cuenta, podría acceder a las asignaciones indirectamente.
- Una persona con control técnico del servidor puede cambiar el código o inspeccionar memoria y obtener las parejas. Esta solución evita que un administrador **normal** pueda verlas mediante la aplicación, pero no proporciona privacidad criptográfica frente a un administrador técnico malicioso. Para ese nivel hace falta un sistema descentralizado o cifrado extremo a extremo con claves privadas administradas individualmente por participantes.
- Un mensaje **aceptado por SMTP** no implica que haya llegado a la bandeja de entrada o que se haya leído. No existe confirmación automática de lectura.

## Seguridad y operación

Mantén la aplicación en la computadora del organizador. No publiques la interfaz administrativa en internet sin autenticación, HTTPS y medidas de seguridad apropiadas. No subas contraseñas al repositorio ni tomes capturas que las expongan. Los participantes no necesitan acceder a Streamlit.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest test_sorteo.py -v
```
