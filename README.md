# 🐳 Aula 15 — Stack de Monitoramento de Containers

Stack didático completo de observabilidade usando Docker Compose.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    Rede Docker: monitoring                    │
│                                                               │
│  ┌──────────┐  scrape   ┌────────────┐  scrape  ┌─────────┐ │
│  │Prometheus│◄──────────│  cAdvisor  │          │  Node   │ │
│  │  :9090   │◄──────────┤ containers │◄─────────│Exporter │ │
│  └────┬─────┘           └────────────┘          │  :9100  │ │
│       │ query                                    └─────────┘ │
│  ┌────▼─────┐  query    ┌────────────┐  push    ┌─────────┐ │
│  │ Grafana  │◄──────────│    Loki    │◄─────────│Promtail │ │
│  │  :3000   │           │   :3100    │          │  agent  │ │
│  └──────────┘           └────────────┘          └────┬────┘ │
│                                                       │      │
│  ┌──────────┐                                    reads│logs  │
│  │  Nginx   │──────────────────────────────── /var/lib/docker│
│  │  :8080   │  (gera tráfego e logs)                  │      │
│  └──────────┘                                         │      │
└─────────────────────────────────────────────────────────────┘
```

## Pré-requisitos

- Docker Engine 24+ e Docker Compose v2
- Linux ou macOS (os bind mounts do cAdvisor/Node Exporter exigem acesso ao host)
- Portas livres: 3000, 3100, 8080, 8081, 9090, 9100

> **Windows:** Use WSL2 com Docker Desktop. Os bind mounts `/proc`, `/sys` e
> `/var/lib/docker` funcionam dentro do ambiente WSL2.

---

## Subindo o stack

```bash
# Entre na pasta do projeto
cd monitoring-stack

# Sobe todos os serviços em background
docker compose up -d

# Acompanhe os logs de inicialização (Ctrl+C para sair)
docker compose logs -f
```

## URLs de acesso

| Serviço    | URL                      | Credenciais  |
|------------|--------------------------|--------------|
| Grafana    | http://localhost:3000    | admin / admin |
| Prometheus | http://localhost:9090    | —            |
| cAdvisor   | http://localhost:8081    | —            |
| App Nginx  | http://localhost:8080    | —            |
| Loki API   | http://localhost:3100    | —            |

---

## Comandos úteis para a demonstração

### Ver logs em tempo real de um container específico
```bash
# Logs do nginx (gera entradas a cada acesso)
docker logs -f nginx-app

# Logs do Prometheus
docker logs -f prometheus

# Todos os serviços ao mesmo tempo
docker compose logs -f
```

### Forçar uso de CPU (para ver nos gráficos de métricas)
```bash
# Cria carga de CPU por 60 segundos usando stress-ng
docker run --rm --name stress-test \
  polinux/stress-ng stress-ng --cpu 2 --timeout 60s

# Alternativa: loop de cálculo em bash puro
docker exec nginx-app sh -c "for i in \$(seq 1 1000000); do echo \$i > /dev/null; done"
```

### Gerar tráfego HTTP no nginx (para aparecer nos logs do Loki)
```bash
# 100 requisições com curl em loop
for i in $(seq 1 100); do curl -s http://localhost:8080 > /dev/null; done

# Usando hey (se instalado) — 200 requisições, 10 concorrentes
hey -n 200 -c 10 http://localhost:8080
```

### Verificar targets do Prometheus (todos devem estar UP)
```
http://localhost:9090/targets
```

### Verificar saúde dos serviços
```bash
# Status de todos os containers
docker compose ps

# Health check individual
docker inspect --format='{{.State.Health.Status}}' prometheus
docker inspect --format='{{.State.Health.Status}}' grafana
docker inspect --format='{{.State.Health.Status}}' loki
```

---

## Queries para demonstração

### PromQL — Prometheus / Grafana (datasource: Prometheus)

```promql
# CPU total de todos os containers (%)
sum(rate(container_cpu_usage_seconds_total{name!=""}[5m])) by (name) * 100

# Memória RAM usada por cada container
container_memory_usage_bytes{name!=""}

# CPU do host (%)
100 - (avg by (instance)(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memória disponível no host
node_memory_MemAvailable_bytes

# Número de containers em execução
count(container_last_seen{name!=""})

# Taxa de requisições HTTP recebidas pelo nginx (requer nginx-prometheus-exporter)
rate(nginx_http_requests_total[5m])
```

### LogQL — Loki (via Grafana → Explore → Loki)

```logql
# Todos os logs dos containers Docker
{job="docker"}

# Apenas logs do nginx
{job="docker", tag="nginx-app"}

# Filtrar por palavra-chave (ex: erros 404)
{job="docker"} |= "404"

# Logs do sistema operacional host
{job="varlogs"}

# Contar linhas de log por container nos últimos 5 minutos
sum by (tag) (count_over_time({job="docker"}[5m]))

# Extrair código de status HTTP dos logs do nginx e filtrar só os erros
{tag="nginx-app"} | pattern `<_> "<method> <path> <_>" <status> <_>` | status >= 400
```

---

## Importar dashboard "Docker and system monitoring" (ID 893)

1. Acesse o Grafana: http://localhost:3000 (admin/admin)
2. No menu lateral, clique em **Dashboards** → **New** → **Import**
3. No campo **"Import via grafana.com"**, digite: `893`
4. Clique em **Load**
5. Em **Prometheus**, selecione o datasource **Prometheus** (já configurado)
6. Clique em **Import**
7. O dashboard estará disponível com gráficos de CPU, RAM, disco e rede

> **Outros dashboards recomendados:**
> - `1860` — Node Exporter Full (métricas detalhadas do host)
> - `14282` — Cadvisor Exporter (métricas de containers)
> - `13639` — Logs / App Dashboard (Loki)

---

## Parando o stack

```bash
# Para todos os containers (mantém os volumes/dados)
docker compose down

# Para E apaga todos os dados (volumes)
docker compose down -v

# Para um serviço específico
docker compose stop grafana
```

---

## Estrutura de arquivos

```
monitoring-stack/
├── docker-compose.yml                        # Orquestração de todos os serviços
├── prometheus/
│   └── prometheus.yml                        # Scrape targets (o que monitorar)
├── loki/
│   └── loki-config.yml                       # Config do servidor de logs
├── promtail/
│   └── promtail-config.yml                   # Coleta de logs dos containers
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── datasources.yml               # Prometheus + Loki configurados automaticamente
│   │   └── dashboards/
│   │       └── dashboards.yml                # Loader de dashboards JSON
│   └── dashboards/
│       └── (coloque aqui seus .json)
└── app/
    └── index.html                            # Página de exemplo servida pelo nginx
```

---

## Troubleshooting

**cAdvisor não inicia / erro de permissão:**
```bash
# Verifique se o Docker tem acesso aos paths necessários
ls -la /var/lib/docker/containers
```

**Loki não aceita logs:**
```bash
# Veja os logs do Promtail para diagnóstico
docker logs promtail

# Verifique se o Loki está pronto
curl http://localhost:3100/ready
```

**Prometheus com targets DOWN:**
```bash
# Acesse http://localhost:9090/targets e verifique a mensagem de erro
# Certifique-se que os containers estão na mesma rede
docker network inspect monitoring
```

**Grafana não carrega os datasources:**
```bash
# Reinicie o Grafana após garantir que Prometheus e Loki estão saudáveis
docker compose restart grafana
```
