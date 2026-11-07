"""
Un solo comando para correr las pruebas y ver los resultados. Desde infra/:

    python medir.py --modelo gemini     # con el GEMINI_API_KEY de .env (unos 30 minutos)
    python medir.py --modelo ollama     # con el modelo local en la GPU (unos 30 minutos)
    python medir.py --modelo simulado   # sin modelo real ni gasto (unos 15 minutos)
    python medir.py --resumen           # solo muestra otra vez los últimos resultados

Opciones: --rapido (solo calibración y T02/T03), --pruebas T01,T05, --versiones secure,
--solo-calibrar, --sin-calibrar, --apagar (baja todo al terminar).

Los resultados quedan en pruebas/resultados/: <modelo>.json y calibracion-<modelo>.json, más
resumen.md con las tablas. Estas pruebas borran las cuotas y la caché de Valkey.

Solo ataca servicios de este mismo Docker Compose. Con Gemini las llamadas sí llegan a Google,
pero el medidor respeta su tiempo de espera y corta en MEDICION_TOPE_TOKENS.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RESULTADOS = AQUI / "pruebas" / "resultados"

MODELOS = {
    "simulado": {
        "perfil": "simulado.env",
        "ataques": ["--segundos", "15", "--segundos-t04", "120", "--segundos-t05", "60", "--estudiantes", "3", "--intervalo-estudiante", "20"],
        "calibrar": ["--intervalo", "1"],
    },
    "gemini": {
        "perfil": "gemini.env",
        "destino": {"DESTINO_URL": "https://generativelanguage.googleapis.com/v1beta/openai", "DESTINO_MODELO": "gemini-3.5-flash-lite", "DESTINO_TIMEOUT": "45"},
        # primero lo que más aporta, por si se acaba la cuota del día a mitad de corrida
        "orden": "T02,T03,T05,T01,T04",
        "llave": "GEMINI_API_KEY",
        # capa gratuita: 15 llamadas por minuto. 3 estudiantes cada 20 s son 9 por minuto, y deja
        # espacio para lo que le quede al atacante. Con esto el p95 tiene unas 27 muestras por fase.
        "ataques": ["--segundos", "60", "--segundos-t04", "120", "--segundos-t05", "180", "--estudiantes", "3", "--intervalo-estudiante", "20", "--pausa", "65"],
        "calibrar": ["--intervalo", "5.5", "--rpm-proveedor", "15", "--rpd-proveedor", "500"],
    },
    "ollama": {
        "perfil": "ollama.env",
        "destino": {"DESTINO_URL": "http://ollama:11434/v1", "DESTINO_MODELO": "qwen2.5:1.5b"},
        "ataques": ["--segundos", "60", "--segundos-t04", "120", "--segundos-t05", "180", "--estudiantes", "3", "--intervalo-estudiante", "20"],
        "calibrar": ["--intervalo", "1"],
    },
}
# Precio de lista por millón de tokens (entrada, salida), de aistudio.google.com/docs/pricing
PRECIOS_GEMINI = {"gemini-3.1-flash-lite": ("0.25", "1.50"), "gemini-3.5-flash-lite": ("0.30", "2.50")}
TOPE_TOKENS = "2000000"  # unos 3 dólares a precio de lista, por si la llave llegara a tener facturación


def leer_env(ruta: Path) -> dict:
    valores = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip()
    return valores


def tiene_gpu() -> bool:
    return shutil.which("nvidia-smi") is not None and subprocess.run(["nvidia-smi"], capture_output=True).returncode == 0


class Stack:
    def __init__(self, modelo: str, gemini_modelo: str | None = None):
        self.modelo = modelo
        self.conf = MODELOS[modelo]
        self.base = ["docker", "compose", "--env-file", ".env", "--env-file", f"perfiles/{self.conf['perfil']}"]
        if modelo == "ollama" and tiene_gpu():
            self.base += ["-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml"]
        self.base += ["--profile", "pruebas"] + (["--profile", "ollama"] if modelo == "ollama" else [])
        # las variables del proceso le ganan a los --env-file: así no se toca .env ni la llave se imprime
        self.env = {**os.environ, "LITELLM_CONFIG": "config.mock.yaml", "DESTINO_URL": "", "DESTINO_KEY": "", "DESTINO_MODELO": "", "MEDICION_TOPE_TOKENS": "0"}
        if "destino" in self.conf:
            self.env.update(self.conf["destino"], LITELLM_CONFIG="config.medicion.yaml", MEDICION_TOPE_TOKENS=TOPE_TOKENS)
        if "llave" in self.conf:
            llave = leer_env(AQUI / ".env").get(self.conf["llave"], "")
            if not llave:
                sys.exit(f"Falta {self.conf['llave']} en infra/.env")
            self.env["DESTINO_KEY"] = llave
        if modelo == "gemini" and gemini_modelo:
            self.env["DESTINO_MODELO"] = gemini_modelo
            if gemini_modelo in PRECIOS_GEMINI:
                self.env["PRECIO_ENTRADA_USD_1M"], self.env["PRECIO_SALIDA_USD_1M"] = PRECIOS_GEMINI[gemini_modelo]

    def correr(self, *args, entrada=None, chequear=True) -> int:
        r = subprocess.run([*self.base, *args], cwd=AQUI, env=self.env, stdin=entrada)
        if chequear and r.returncode:
            sys.exit(f"Falló: docker compose {' '.join(args)}")
        return r.returncode

    def levantar(self) -> None:
        paso("Levantando los contenedores")
        self.correr("up", "-d", "--build", "--wait", "--wait-timeout", "300")
        if self.modelo == "ollama":
            modelo = self.conf["destino"]["DESTINO_MODELO"]
            paso(f"Descargando (si falta) y calentando {modelo}")
            self.correr("exec", "-T", "ollama", "ollama", "pull", modelo)
            self.correr("exec", "-T", "ollama", "ollama", "run", modelo, "hola")

    def apagar(self) -> None:
        self.correr("down", chequear=False)


def paso(texto: str) -> None:
    print(f"\n=== {texto} ===", flush=True)


def cargar(nombre: str) -> dict | None:
    ruta = RESULTADOS / f"{nombre}.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def miles(n) -> str:
    return "-" if n is None else f"{n:,.0f}".replace(",", ".")


def cambio(antes, despues) -> str:
    return f"{100 * (despues - antes) / antes:+.1f}%".replace(".", ",") if antes else "-"


def tabla(filas: list[list[str]]) -> str:
    anchos = [max(len(str(f[i])) for f in filas) for i in range(len(filas[0]))]
    lineas = ["| " + " | ".join(str(c).ljust(a) for c, a in zip(f, anchos)) + " |" for f in filas]
    lineas.insert(1, "|" + "|".join("-" * (a + 2) for a in anchos) + "|")
    return "\n".join(lineas)


def resumen_ataques(modelo: str, d: dict) -> str:
    filas = [["Prueba", "Sin controles", "Con controles", "Cambio"]]
    for prueba, titulo in (("T01", f"T01 Flooding {d.get('segundos', 0):.0f} s, tokens"), ("T04", f"T04 Ráfaga 30 IP {d.get('segundos_t04', 0):.0f} s, tokens")):
        if prueba in d and "unsecure" in d[prueba] and "secure" in d[prueba]:
            u, s = d[prueba]["unsecure"], d[prueba]["secure"]
            filas.append([titulo, miles(u["tokens"]), miles(s["tokens"]), cambio(u["tokens"], s["tokens"])])
            filas.append([f"    llamadas que llegaron al modelo", miles(u["llamadas_llm"]), miles(s["llamadas_llm"]), cambio(u["llamadas_llm"], s["llamadas_llm"])])
            filas.append([f"    rechazadas por el proveedor", miles(u["rechazos_proveedor"]), miles(s["rechazos_proveedor"]), ""])
    if "T02" in d and "unsecure" in d["T02"] and "secure" in d["T02"]:
        u, s = d["T02"]["unsecure"], d["T02"]["secure"]
        filas.append(["T02 \"Resume todo\", tokens", miles(u["tokens_totales_masiva"]), miles(s["tokens_totales_masiva"]), cambio(u["tokens_totales_masiva"], s["tokens_totales_masiva"])])
        filas.append(["    tokens de entrada (lo que sí controlamos)", miles(u["tokens_entrada_masiva"]), miles(s["tokens_entrada_masiva"]), cambio(u["tokens_entrada_masiva"], s["tokens_entrada_masiva"])])
        filas.append(["    fragmentos enviados", miles(u["fragmentos"]), miles(s["fragmentos"]), ""])
        filas.append(["    prompt gigante, tokens", miles(u["tokens_prompt_gigante"]), f"{miles(s['tokens_prompt_gigante'])} (HTTP {s['estado_prompt_gigante']})", ""])
    if "T03" in d and "unsecure" in d["T03"] and "secure" in d["T03"]:
        u, s = d["T03"]["unsecure"], d["T03"]["secure"]
        filas.append(["T03 Pregunta repetida, tokens", miles(u["tokens"]), miles(s["tokens"]), cambio(u["tokens"], s["tokens"])])
        filas.append(["    aciertos de caché (igual/reformulada)", f"{u['aciertos_repetida']}, {u['aciertos_reformulada']}", f"{s['aciertos_repetida']}, {s['aciertos_reformulada']}", ""])
    if "T05" in d and "unsecure" in d["T05"] and "secure" in d["T05"]:
        u, s = d["T05"]["unsecure"], d["T05"]["secure"]
        filas.append(["T05 Estudiantes respondidos con ataque", f"{u['con_ataque_pct_exito']}%", f"{s['con_ataque_pct_exito']}%", ""])
        filas.append(["    latencia p95 sin ataque", f"{u['sin_ataque_p95_s']} s", f"{s['sin_ataque_p95_s']} s", ""])
        filas.append(["    latencia p95 con ataque", f"{u['con_ataque_p95_s']} s" if u["muestras_con_ataque"] else "sin respuestas", f"{s['con_ataque_p95_s']} s" if s["muestras_con_ataque"] else "sin respuestas", ""])
        filas.append(["    muestras con ataque", u["muestras_con_ataque"], s["muestras_con_ataque"], ""])
    texto = f"## {modelo} ({d.get('modelo')})  {d.get('fecha', '')[:16]}\n\n" + tabla(filas)
    if "T04" in d and "secure" in d["T04"]:
        s = d["T04"]["secure"]
        u = d["T04"].get("unsecure", {})
        texto += f"\n\nT04, estudiante respondido durante el ataque: sin controles {u.get('estudiante_durante_pct_exito')}%, con controles {s.get('estudiante_durante_pct_exito')}%"
        texto += f"\nT04, estudiante nuevo después del ataque: HTTP {s.get('estudiante_despues')}"
    if d.get("detenida_por"):
        texto += f"\n\nCORRIDA INCOMPLETA: {d['detenida_por']}"
    return texto


def resumen_calibracion(modelo: str, c: dict) -> str:
    t, s = c["tokens_total"], c["segundos"]
    filas = [["Variable sugerida", "Valor"]] + [[k, miles(v)] for k, v in c["sugerido"].items()]
    # el simulador responde siempre lo mismo: contar respuestas correctas ahí no dice nada
    correctas = "no aplica" if c["modelo"] == "simulado" else c["correctas"]
    return (
        f"## Calibración con {modelo} ({c['modelo']})\n\n"
        f"Preguntas: {c['preguntas']}, correctas: {correctas}, cortadas por el tope de salida: {c['truncadas']}\n"
        f"Tokens por pregunta: mediana {miles(t['mediana'])}, p95 {miles(t['p95'])}, máximo {miles(t['max'])}\n"
        f"Errores del proveedor: {c.get('errores_proveedor', 0)}\n"
        f"Latencia: mediana {s['mediana']} s, p95 {s['p95']} s (el modelo: mediana {c.get('segundos_modelo', {}).get('mediana')} s, la búsqueda: {c.get('segundos_busqueda', {}).get('mediana')} s)\n\n" + tabla(filas)
    )


def imprimir_resumen() -> str:
    partes = []
    for ruta in sorted(RESULTADOS.glob("calibracion-*.json")):
        partes.append(resumen_calibracion(ruta.stem.removeprefix("calibracion-"), cargar(ruta.stem)))
    for ruta in sorted(RESULTADOS.glob("*.json")):
        if not ruta.stem.startswith("calibracion-"):
            partes.append(resumen_ataques(ruta.stem, cargar(ruta.stem)))
    texto = "\n\n".join(partes) or "Todavía no hay resultados: corre python medir.py --modelo simulado"
    print("\n" + texto)
    (RESULTADOS / "resumen.md").write_text(texto + "\n", encoding="utf-8")
    return texto


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    a = argparse.ArgumentParser(description="Corre las pruebas y muestra los resultados")
    a.add_argument("--modelo", choices=MODELOS, default="simulado")
    a.add_argument("--resumen", action="store_true", help="solo muestra los últimos resultados")
    a.add_argument("--rapido", action="store_true", help="solo calibración, T02 y T03")
    a.add_argument("--pruebas", help="por ejemplo T01,T05")
    a.add_argument("--versiones", help="unsecure, secure o las dos")
    a.add_argument("--solo-calibrar", action="store_true")
    a.add_argument("--sin-calibrar", action="store_true")
    a.add_argument("--salida", help="nombre del archivo de resultados (por defecto, el modelo)")
    a.add_argument("--gemini-modelo", help="otro modelo de Gemini: la cuota gratuita de 500 al día es por modelo")
    a.add_argument("--apagar", action="store_true", help="baja todo al terminar")
    args = a.parse_args()

    if args.resumen:
        imprimir_resumen()
        return

    stack = Stack(args.modelo, args.gemini_modelo)
    inicio = time.time()
    stack.levantar()
    salida = args.salida or args.modelo

    fallas = 0
    if args.modelo == "simulado" and not (args.pruebas or args.solo_calibrar):
        paso("Comprobando cada control")
        fallas += bool(stack.correr("exec", "-T", "atacante", "python", "comprobaciones.py", chequear=False))
    paso("Comprobando el aislamiento de la red")
    with open(AQUI / "pruebas" / "aislamiento.py", "rb") as f:
        fallas += bool(stack.correr("exec", "-T", "orquestador", "python", "-", entrada=f, chequear=False))

    if not args.sin_calibrar:
        paso("Calibración: costo y calidad de una pregunta normal")
        stack.correr("exec", "-T", "atacante", "python", "calibrar.py", "--salida", salida, *stack.conf["calibrar"])

    if not args.solo_calibrar:
        pruebas = args.pruebas or ("T02,T03" if args.rapido else stack.conf.get("orden", "T01,T02,T03,T04,T05"))
        paso(f"Ataques {pruebas}")
        extra = ["--versiones", args.versiones] if args.versiones else []
        stack.correr("exec", "-T", "atacante", "python", "ataques.py", "--pruebas", pruebas, "--salida", salida, *extra, *stack.conf["ataques"])

    print(f"\nTerminó en {(time.time() - inicio) / 60:.1f} minutos.")
    imprimir_resumen()
    if fallas:
        print(f"\nOJO: {fallas} grupo(s) de comprobaciones fallaron, revisa la salida de arriba.")
    if args.apagar:
        stack.apagar()
    else:
        print("\nEl sistema sigue arriba. Chat: http://localhost:8080  Grafana: http://localhost:3000")
        print("Para apagarlo: docker compose --profile pruebas --profile ollama down")
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    main()
