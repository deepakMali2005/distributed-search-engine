FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/root/.cache/huggingface

WORKDIR /app

COPY requirements.txt .

# Install CPU-only PyTorch first so pip does not resolve
# the CUDA-enabled PyTorch distribution.
RUN pip install --upgrade pip \
    && pip install --no-cache-dir \
       torch \
       --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/index/shards \
    /root/.cache/huggingface

EXPOSE 8000 8001

CMD ["python", "-m", "services.search_api.main"]