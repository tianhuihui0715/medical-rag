# 构建包含两个本地 BGE 模型的应用镜像，数据库配置在运行时挂载。
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    TOKENIZERS_PARALLELISM=false \
    HOME=/tmp \
    HF_HOME=/tmp/huggingface

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 tini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# 先安装 CPU 版，避免在不使用 CUDA 的容器中引入 GPU 运行库。
RUN python -m pip install --no-cache-dir torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir -r requirements.txt
# MySQL 8 首次认证需要 RSA 支持，独立安装便于复用较大的模型依赖层。
RUN python -m pip install --no-cache-dir 'PyMySQL[rsa]==1.1.1'

COPY main.py .
COPY clint/ clint/
COPY common/ common/
COPY controller/ controller/
COPY dao/ dao/
COPY model/ model/
COPY parser/ parser/
COPY service/ service/
COPY splitter/ splitter/
COPY task/ task/
COPY docker/ docker/
COPY --chown=10001:10001 models/ models/

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/openapi.json', timeout=3)"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "docker/start.py"]
