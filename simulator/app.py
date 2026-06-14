"""
Simulator API — Aula 15
Gera logs, carga de CPU e uso de memória para demonstração didática
Todos os logs vão para stdout e são capturados pelo Promtail → Loki
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
import random
import logging
import sys

# =============================================================================
# Configuração de logging para stdout (Docker captura e o Promtail lê)
# =============================================================================
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s [simulator] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    force=True
)
logger = logging.getLogger('simulator')

app = Flask(__name__)
CORS(app)  # Permite chamadas cross-origin do browser (porta 8080 → 5000)

# =============================================================================
# Banco de mensagens de log simuladas
# =============================================================================
LOG_MESSAGES = {
    'INFO': [
        "Usuário autenticado com sucesso — id={}",
        "Requisição processada em {}ms — status=200",
        "Cache hit para chave session:{}",
        "Relatório gerado com {} registros",
        "Backup concluído — {} arquivos processados",
        "Conexão com banco estabelecida — pool={}",
        "Arquivo de configuração recarregado — versão {}",
    ],
    'WARN': [
        "Latência alta detectada: {}ms (limite recomendado: 500ms)",
        "Pool de conexões {}% utilizado — considere aumentar o tamanho",
        "Token JWT expira em {} minuto(s) — renovação necessária",
        "Tentativa #{} de reconexão ao serviço externo",
        "Fila com {} mensagens pendentes — processamento lento",
        "Disco {}% utilizado — verifique uso de armazenamento",
        "Rate limit: {} req/s — próximo do limite configurado",
    ],
    'ERROR': [
        "Falha ao conectar no banco de dados — timeout após {}s",
        "NullPointerException em UserService.process() linha {}",
        "Arquivo não encontrado: /data/config_{}.json",
        "Autenticação falhou — token inválido (tentativa #{})",
        "Serviço externo retornou HTTP {} — falha na integração",
        "Deadlock detectado na transação #{} — rollback executado",
        "Falha ao escrever no disco — código de erro {}",
    ],
}


# =============================================================================
# Funções de background (rodam em threads separadas)
# =============================================================================

def _log_batch(level: str, count: int):
    """Gera `count` entradas de log no nível especificado."""
    msgs = LOG_MESSAGES.get(level, LOG_MESSAGES['INFO'])
    for _ in range(count):
        val = random.randint(1, 9999)
        msg = random.choice(msgs).format(val)
        if level == 'INFO':
            logger.info(msg)
        elif level == 'WARN':
            logger.warning(msg)
        elif level == 'ERROR':
            logger.error(msg)
        time.sleep(0.08)


def _cpu_worker(duration: int, thread_id: str):
    """Realiza cálculos intensivos para gerar carga real de CPU."""
    end = time.time() + duration
    logger.warning(f"[CPU] Thread-{thread_id} iniciada — duração: {duration}s")
    cycles = 0
    while time.time() < end:
        # Cálculo pesado — visível no cAdvisor e Prometheus
        _ = sum(i * i for i in range(60000))
        cycles += 1
    logger.info(f"[CPU] Thread-{thread_id} finalizada — {cycles} ciclos executados")


def _memory_worker(mb: int, duration: int):
    """Aloca `mb` megabytes de memória por `duration` segundos."""
    logger.warning(f"[MEMORY] Iniciando alocação de {mb}MB por {duration}s")
    try:
        data = bytearray(mb * 1024 * 1024)
        # Força a alocação real (evita lazy allocation do SO)
        for i in range(0, len(data), 4096):
            data[i] = 1
        logger.warning(f"[MEMORY] {mb}MB alocados com sucesso — aguardando {duration}s")
        time.sleep(duration)
        del data
        import gc
        gc.collect()
        logger.info(f"[MEMORY] {mb}MB liberados da memória")
    except MemoryError:
        logger.error(f"[MEMORY] MemoryError — não foi possível alocar {mb}MB")


# =============================================================================
# Endpoints da API
# =============================================================================

@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "simulator"})


@app.route('/api/logs')
def api_logs():
    """Gera logs em lote no nível especificado."""
    level = request.args.get('level', 'INFO').upper()
    count = min(int(request.args.get('count', 10)), 100)

    if level not in LOG_MESSAGES:
        return jsonify({"error": f"Nível inválido: {level}"}), 400

    threading.Thread(target=_log_batch, args=(level, count), daemon=True).start()
    logger.info(f"[API] Gerando {count} logs nível {level}")
    return jsonify({"status": "generating", "level": level, "count": count})


@app.route('/api/cpu')
def api_cpu():
    """Inicia threads de stress de CPU."""
    duration = min(int(request.args.get('duration', 30)), 60)
    threads  = min(int(request.args.get('threads', 2)), 4)

    for i in range(threads):
        threading.Thread(
            target=_cpu_worker,
            args=(duration, chr(65 + i)),  # Thread-A, Thread-B, ...
            daemon=True
        ).start()

    logger.warning(f"[CPU] Stress iniciado — {threads} thread(s) × {duration}s")
    return jsonify({"status": "started", "duration": duration, "threads": threads})


@app.route('/api/memory')
def api_memory():
    """Aloca memória temporariamente."""
    mb       = min(int(request.args.get('mb', 200)), 512)
    duration = min(int(request.args.get('duration', 15)), 60)

    threading.Thread(target=_memory_worker, args=(mb, duration), daemon=True).start()
    return jsonify({"status": "started", "mb": mb, "duration": duration})


@app.route('/api/mix')
def api_mix():
    """Executa todos os testes simultaneamente — cenário completo."""
    logger.warning("[MIX] ========== SIMULAÇÃO COMPLETA INICIADA ==========")

    threading.Thread(target=_log_batch, args=('INFO',  20), daemon=True).start()
    threading.Thread(target=_log_batch, args=('WARN',  10), daemon=True).start()
    threading.Thread(target=_log_batch, args=('ERROR',  5), daemon=True).start()
    threading.Thread(target=_cpu_worker, args=(30, 'A'), daemon=True).start()
    threading.Thread(target=_cpu_worker, args=(30, 'B'), daemon=True).start()
    threading.Thread(target=_memory_worker, args=(200, 25), daemon=True).start()

    return jsonify({
        "status": "mix started",
        "components": ["INFO×20", "WARN×10", "ERROR×5", "CPU×2 (30s)", "Memory 200MB (25s)"]
    })


# =============================================================================
# Inicialização
# =============================================================================
if __name__ == '__main__':
    logger.info("=== Simulator API iniciada na porta 5000 ===")
    app.run(host='0.0.0.0', port=5000, threaded=True)
