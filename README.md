# Laboratorio 3

## Estudiantes
- Victor Salinas, 202204580-9
- Verónica Torres, 202373503-5



## Especificación de algoritmos y desarrollo realizado.

Se desarrolló un sistema distribuido mediante hebras para simular un proceso de extracción de fragmentos criptográficos. El desarrollo se estructura en un ciclo de 8 rondas , gestionado por la clase principal Sistema, la cual coordina 64 hebras de la clase Bot interactuando con 16 instancias de la clase Servidor.

Algoritmo de Prioridad y Selección de Servidor: Se abandonó la selección aleatoria para implementar una prioridad dinámica. Al inicio de la fase de exploración, las hebras entran en un estado de latencia proporcional a la cantidad de fragmentos en su búfer. Simultáneamente, el algoritmo ordena la lista de servidores de mayor a menor según sus fragmentos disponibles (sorted(key=lambda s: s.fragmentos, reverse=True)). El bot intenta acceder al primer servidor de la lista que no esté saturado.

Algoritmo de Daño y Colisión: Al ingresar a un servidor, se simula una extracción de 1 a 3 fragmentos. El sistema evalúa la cantidad de bots presentes (num_bots_presentes). Si hay concurrencia, se calcula un 30% de probabilidad de colisión de paquetes (sin extracción y pérdida de 10 puntos de integridad). En caso de éxito, el firewall del servidor descuenta integridad equivalente a su defensa dividida por los bots presentes (defensa/número_de_bots_en_servidor).

Algoritmo de Estados e Intercambio: Se establecen reglas de transición al final de cada ronda. Si la integridad cae a <=20, el bot se bloquea por una ronda recuperando 30 puntos. Si es <0, se elimina. Si un bot activo y uno bloqueado coinciden en un servidor, se ejecuta un algoritmo de transferencia de hasta 3 fragmentos, otorgando 15 puntos de integridad al receptor.

## Instrucciones para compilar y correr código.

Ejecutar desde sistema operativo Linux con Python 3.
En el directorio donde se encuentra el código fuente ejecutar a través
de la terminal con : python3 LAB3_Salinas_Torres.py

El programa retendrá la consola durante un mínimo de 120 segundos (8 rondas de 15 segundos reales). Al finalizar, generará los archivos de texto correspondientes en el mismo directorio (inicializacion.txt, ronda_X.txt, intercambios.txt, extraccion_final.txt).

## Estrategias de sincronización implementadas.

threading.Barrier(): Se utilizan dos barreras inicializadas con el número total de bots más el hilo principal. Estas barreras imponen la sincronización estricta al inicio y al final de cada ronda de extracción, permitiendo que el hilo central detenga la ejecución durante 15 segundos exactos sin que las hebras se desfasen en el tiempo.

threading.Semaphore(): Implementado en cada servidor (Semaphore(8)). Se utiliza para controlar el ancho de banda y garantizar que, bajo ninguna circunstancia, ingresen más de 8 bots de manera simultánea a un clúster. El semáforo se protege con una estructura try...finally para evitar interbloqueos en caso de finalización anormal de la hebra.

threading.Lock(): Se emplean múltiples candados lógicos:
Un Lock para proteger la consola y la escritura de archivos de I/O, evitando condiciones de carrera que generen líneas de texto truncadas.

Un Lock interno en los servidores para proteger y actualizar atómicamente la lista de bots conectados (bots_en_servidor).

Un Lock para asegurar la consistencia del inventario global al restar fragmentos extraídos, previniendo extracciones simultáneas del mismo recurso.

## Supuestos.

Sincronización del Firewall: Para cumplir la instrucción de "operar en simultáneo" frente al firewall, se asume la necesidad de una pausa microscópica (time.sleep(0.5)) inmediatamente después de que el bot adquiere el semáforo. Esto permite agrupar a las hebras que entraron casi al mismo tiempo para que el cálculo del daño (defensa / bots) sea matemáticamente equitativo.

Colisión Restringida: Se asume lógicamente que la probabilidad del 30% de colisión  únicamente se calcula cuando la hebra detecta que num_bots_presentes > 1. Si un bot entra a un servidor vacío, no se expone a choques de red.

En el PDF dice que el nombre del archivo debe ser "LAB4_..." asumimos que es un error ya que este es el lab 3, asi que el nombre del archivo lo dejamos como "LAB3_...".