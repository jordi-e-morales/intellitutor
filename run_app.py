"""
Script de arranque para solo Flask (UI y chat nativo).
Conservado para compatibilidad local.
"""
import subprocess
import sys


def run_flask():
    # Usa el ejecutable de Python del entorno actual para evitar problemas de módulos
    subprocess.run([sys.executable, "auth_app.py"])  # Arranca Flask en :5000


if __name__ == "__main__":
    print("🚀 Iniciando Tutor Educativo (Flask UI)...")
    print("📱 Flask: http://localhost:5000")
    run_flask()
