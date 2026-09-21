#!/usr/bin/env bash
# 可观测性相关单元测试（手动执行）。
#
# 前置条件：
#   1. 安装依赖：pip install -r requirements.txt
#      （新增：opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http,
#       prometheus-client, redis, structlog）
#   2. 在仓库根目录执行：./test.sh
#
# 可选环境变量（用于手动验证集成行为）：
#   OTEL_ENABLED=True OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
#   REDIS_URL=redis://localhost:6379/0
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "==> 1/5 新增可观测性库单元测试 (hc.lib.tests.test_observability)"
"$PYTHON" manage.py test hc.lib.tests.test_observability -v 2

echo "==> 2/5 健康检查端点测试 (hc.api.tests.test_health)"
"$PYTHON" manage.py test hc.api.tests.test_health -v 2

echo "==> 3/5 Prometheus /metrics 端点测试 (hc.api.tests.test_prometheus_metrics)"
"$PYTHON" manage.py test hc.api.tests.test_prometheus_metrics -v 2

echo "==> 4/5 受影响的既有测试回归 (ping / sendalerts / notify)"
"$PYTHON" manage.py test \
    hc.api.tests.test_ping \
    hc.api.tests.test_ping_by_slug \
    hc.api.tests.test_sendalerts \
    hc.api.tests.test_notify \
    hc.api.tests.test_check_model \
    -v 1

echo "==> 5/5 手动冒烟检查（可选，需服务运行）"
cat <<'EOF'
以下命令用于手动冒烟验证（先运行 manage.py runserver）：

  # 健康检查端点（数据库 / S3 / SMTP / Redis 连通性）
  curl -s http://localhost:8000/health/ | python3 -m json.tool

  # Prometheus 指标端点
  curl -s http://localhost:8000/metrics | grep -E 'hc_pings_total|hc_db_queries'

  # 触发一次 ping 后再次查看指标
  curl -s "http://localhost:8000/ping/<check-uuid>"
  curl -s http://localhost:8000/metrics | grep hc_pings_total

  # 分布式追踪（需先启动 OTLP Collector，例如 Jaeger:
  #   docker run -p 4318:4318 -p 16686:16686 jaegertracing/all-in-one）
  OTEL_ENABLED=True python3 manage.py runserver
  # 然后访问任意页面，在 http://localhost:16686 查看 trace

  # Grafana 仪表盘：在 Grafana 中导入 grafana/dashboard.json
EOF

echo "全部测试通过。"
