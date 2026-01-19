FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    mafft \
    fasttree \
    iqtree \
    build-essential \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L -o /tmp/trimal.tar.gz https://github.com/inab/trimal/archive/refs/tags/v1.4.1.tar.gz \
    && tar -xzf /tmp/trimal.tar.gz -C /tmp \
    && make -C /tmp/trimal-1.4.1/source \
    && cp /tmp/trimal-1.4.1/source/trimal /usr/local/bin/ \
    && rm -rf /tmp/trimal*

COPY requirements.txt /app/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN mkdir -p /app/uploads /app/results

EXPOSE 8000

ENV PATH="/opt/venv/bin:$PATH"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
