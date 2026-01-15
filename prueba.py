from pywinauto import Desktop
from pywinauto.application import Application
import time

print("Abriendo Archivex...")

ruta = r'"C:\Users\David Merino\AppData\Roaming\Xoborg Studios\Archivex Clinical\Archivex Clinical.exe"'

Application(backend="uia").start(
    f'cmd /c start "" {ruta}',
    wait_for_idle=False
)

time.sleep(15)

# Buscar ventana
ventana = None
for w in Desktop(backend="uia").windows():
    if w.window_text() == "Archivex Clinical" and w.is_visible():
        ventana = w
        break

if not ventana:
    print("❌ No se encontró la ventana")
    exit()

# Forzar foco en ventana
ventana.restore()
ventana.set_focus()
time.sleep(1)

print("✅ Ventana conectada")

# Obtener campos Edit
edits = ventana.descendants(control_type="Edit")
print(f"Se han encontrado {len(edits)} campos Edit\n")

for i, edit in enumerate(edits):
    try:
        print(f"Probando Edit {i}")
        edit.set_text(f"TEST{i}")
        time.sleep(1)
    except Exception as e:
        print(f"❌ No se pudo escribir en Edit {i}: {e}")

time.sleep(10)




