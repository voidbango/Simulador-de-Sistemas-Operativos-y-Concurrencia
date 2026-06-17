import threading
import time
import math
import random

#CONFIGURACION Y CTES.
NUM_SERVIDORES = 16
NUM_BOTS = 64
TOTAL_FRAGMENTOS = 256
MAX_BOTS_POR_SERVIDOR = 8
NUM_RONDAS = 8
CAPACIDAD_BUFFER = 10

#Bloqueo para escritura de archivos y consola
log_lock = threading.Lock()

def safe_log(filename, message):
    with log_lock:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(message + "\n")

# CLASES DEL SIST.

class Servidor:
    def __init__(self, id_serv):
        self.id = id_serv
        self.fragmentos = 0  # Se asignará en inicialización
        self.defensa = random.randint(10, 50)
        self.semaforo = threading.Semaphore(MAX_BOTS_POR_SERVIDOR)
        self.bots_en_servidor = []
        self.lock_bots = threading.Lock() # Para proteger la lista de bots presentes
        self.lock_fragmentos = threading.Lock()

    def registrar_entrada(self, bot_id):
        with self.lock_bots:
            self.bots_en_servidor.append(bot_id)

    def registrar_salida(self, bot_id):
        with self.lock_bots:
            if bot_id in self.bots_en_servidor:
                self.bots_en_servidor.remove(bot_id)

    def get_num_bots(self):
        with self.lock_bots:
            return len(self.bots_en_servidor)

class Bot(threading.Thread):
    def __init__(self, id_bot, sistema):
        super().__init__()
        self.id_bot = id_bot
        self.sistema = sistema
        self.integridad = 100
        self.buffer = 0
        self.estado = "Activo" # "Activo", "Bloqueado", "Eliminado"
        self.rondas_bloqueado = 0
        self.fragmentos_totales_extraidos = 0
        self.servidor_actual = None

    def run(self):
        for ronda in range(1, NUM_RONDAS + 1):
            # Sincronización de inicio de ronda
            # Todos los bots deben llegar aquí, incluso los eliminados, 
            # para no bloquear la barrera.
            self.sistema.barrera.wait()
            
            if self.estado == "Eliminado":
                # Sincronización de fin de ronda para bots eliminados
                self.sistema.barrera_fin_ronda.wait()
                continue

            if self.estado == "Bloqueado":
                self.rondas_bloqueado += 1
                self.integridad += 30
                if self.integridad > 100: self.integridad = 100
                
                log_msg = f"Bot {self.id_bot}: Bloqueado (Recuperando integridad: {self.integridad})"
                self.sistema.registrar_log_ronda(ronda, log_msg)
                
                # Sincronización de fin de ronda para bots bloqueados
                self.sistema.barrera_fin_ronda.wait()
                
                # Al final de la ronda de espera, vuelve a Activo
                self.estado = "Activo"
                continue

            # Fase de Exploración: Prioridad y Movimiento (Regla del PDF)
            # Los bots con menos fragmentos despiertan antes (Prioridad temporal)
            time.sleep(self.buffer * 0.05) 
            
            # Ordenar servidores por mayor disponibilidad de recursos (fragmentos)
            servidores_disp = sorted(self.sistema.servidores, key=lambda s: s.fragmentos, reverse=True)
            
            self.servidor_actual = None
            for serv in servidores_disp:
                # Intenta entrar al servidor con más recursos sin bloquearse indefinidamente
                if serv.semaforo.acquire(blocking=False):
                    self.servidor_actual = serv
                    break
            
            if self.servidor_actual:
                try:
                    self.servidor_actual.registrar_entrada(self.id_bot)
                    
                    # Pausa obligatoria para que todos los bots de esta ronda entren 
                    # y el cálculo de daño sea simultáneo y equitativo para todos.
                    time.sleep(0.5) 
                    
                    self.fase_extraccion(ronda)
                    self.fase_intercambio()
                finally:
                    self.servidor_actual.registrar_salida(self.id_bot)
                    self.servidor_actual.semaforo.release()
            else:
                log_msg = f"Bot {self.id_bot}: No pudo entrar a ningún servidor (Llenos)"
                self.sistema.registrar_log_ronda(ronda, log_msg)

            # Verificación de integridad final de ronda
            if self.integridad < 0:
                self.estado = "Eliminado"
            elif self.integridad <= 20:
                self.estado = "Bloqueado"

            # Sincronización de fin de ronda
            self.sistema.barrera_fin_ronda.wait()

    def fase_extraccion(self, ronda):
        serv = self.servidor_actual
        num_bots_presentes = serv.get_num_bots()
        
        # Daño del servidor
        danio = serv.defensa / num_bots_presentes
        self.integridad -= danio
        
        # Colisión (30% probabilidad)
        if num_bots_presentes > 1 and random.random() < 0.30:
            self.integridad -= 10
            log_msg = f"Bot {self.id_bot}: ¡COLISIÓN en Servidor {serv.id}! Integridad: {self.integridad:.2f}"
            self.sistema.registrar_log_ronda(ronda, log_msg)
            return

        # Extracción (70% éxito si no hubo colisión previa)
        cant_pedida = random.randint(1, 3)
        
        # Costo de extracción
        costos = {1: 5, 2: 12, 3: 20}
        costo = costos[cant_pedida]
        self.integridad -= costo
        
        # Verificar si hay fragmentos disponibles
        extraidos = 0
        with serv.lock_fragmentos:
            extraidos = min(cant_pedida, serv.fragmentos)
            # No exceder buffer
            espacio_buffer = CAPACIDAD_BUFFER - self.buffer
            extraidos = min(extraidos, espacio_buffer)
            
            serv.fragmentos -= extraidos
            self.buffer += extraidos
            self.fragmentos_totales_extraidos += extraidos

        log_msg = f"Bot {self.id_bot}: Servidor {serv.id}, Extraídos {extraidos}, Integridad {self.integridad:.2f}"
        self.sistema.registrar_log_ronda(ronda, log_msg)

    def fase_intercambio(self):
        # Si este bot está activo, busca a uno bloqueado en el mismo servidor
        if self.estado != "Activo":
            return
            
        with self.servidor_actual.lock_bots:
            for other_id in self.servidor_actual.bots_en_servidor:
                if other_id == self.id_bot: continue
                
                other_bot = self.sistema.bots[other_id]
                if other_bot.estado == "Bloqueado":
                    # Intercambio
                    cant = min(3, self.buffer)
                    if cant > 0:
                        self.buffer -= cant
                        other_bot.buffer += cant
                        other_bot.integridad += 15
                        if other_bot.integridad > 100: other_bot.integridad = 100
                        
                        msg = f"Intercambio: Bot {self.id_bot} -> Bot {other_id} ({cant} fragmentos)"
                        with log_lock:
                            with open("intercambios.txt", "a", encoding="utf-8") as f:
                                f.write(msg + "\n")

class Sistema:
    def __init__(self):
        self.servidores = [Servidor(i) for i in range(NUM_SERVIDORES)]
        self.distribuir_fragmentos()
        self.bots = {}
        self.barrera = threading.Barrier(NUM_BOTS + 1)
        self.barrera_fin_ronda = threading.Barrier(NUM_BOTS + 1)
        
        # Limpiar archivos previos
        for f in ["intercambios.txt", "extraccion_final.txt"]:
            open(f, "w").close()
        for r in range(1, NUM_RONDAS + 1):
            open(f"ronda_{r}.txt", "w").close()

    def distribuir_fragmentos(self):
        total = 0
        # Mínimo 10 por servidor
        for s in self.servidores:
            s.fragmentos = 10
            total += 10
        
        # Distribuir los restantes 96
        restantes = TOTAL_FRAGMENTOS - total
        while restantes > 0:
            s = random.choice(self.servidores)
            if s.fragmentos < 20:
                s.fragmentos += 1
                restantes -= 1

    def inicializar_archivos(self):
        content = "--- INICIALIZACIÓN DEL SISTEMA ---\n\n"
        content += "SERVIDORES:\n"
        for s in self.servidores:
            content += f"ID: {s.id}, Fragmentos: {s.fragmentos}, Defensa: {s.defensa}\n"
        
        content += "\nBOTS:\n"
        for i in range(NUM_BOTS):
            content += f"ID: {i}, Integridad: 100, Búfer: 0/10, Estado: Activo\n"
            
        with open("inicializacion.txt", "w", encoding="utf-8") as f:
            f.write(content)

    def registrar_log_ronda(self, ronda, mensaje):
        safe_log(f"ronda_{ronda}.txt", mensaje)

    def ejecutar(self):
        self.inicializar_archivos()
        
        # Crear e iniciar bots
        for i in range(NUM_BOTS):
            bot = Bot(i, self)
            self.bots[i] = bot
            bot.start()

        for ronda in range(1, NUM_RONDAS + 1):
            print(f"Iniciando Ronda {ronda}...")
            self.barrera.wait() # Sincronizar inicio con bots
            
            # Cada ronda dura estrictamente 15 segundos según las instrucciones
            time.sleep(15)
            
            self.barrera_fin_ronda.wait() # Sincronizar fin con bots
            print(f"Fin de Ronda {ronda}.")

        # Esperar a que todos terminen
        for bot in self.bots.values():
            bot.join()

        self.generar_reporte_final()

    def generar_reporte_final(self):
        total_extraidos = sum(b.fragmentos_totales_extraidos for b in self.bots.values())
        bots_activos = [b for b in self.bots.values() if b.estado != "Eliminado"]
        num_activos = len(bots_activos)
        
        ratio = (total_extraidos / num_activos) / 256 if num_activos > 0 else 0
        
        content = "--- REPORTE FINAL DE EXTRACCIÓN ---\n\n"
        content += f"Total de fragmentos extraídos: {total_extraidos}\n"
        content += f"Bots activos: {num_activos}\n"
        content += f"Ratio de recuperación: {ratio:.4f}\n\n"
        
        content += "ESTADO FINAL DE BOTS:\n"
        for b in self.bots.values():
            status = "ELIMINADO" if b.estado == "Eliminado" else f"Búfer: {b.buffer}/10"
            content += f"Bot {b.id_bot}: {status}, Total Extraído: {b.fragmentos_totales_extraidos}\n"
            
        with open("extraccion_final.txt", "w", encoding="utf-8") as f:
            f.write(content)
        print("Simulación finalizada. Archivos generados.")

if __name__ == "__main__":
    sistema = Sistema()
    sistema.ejecutar()
