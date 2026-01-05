# Imagem base com Python
FROM python:3.11-slim

# Metadados
LABEL maintainer="Fomitiporia TreeApp"
LABEL description="Phylogenetic analysis server with MAFFT, IQ-TREE and FastTree"

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    cmake \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar MAFFT
RUN wget https://mafft.cbrc.jp/alignment/software/mafft-7.520-with-extensions-src.tgz && \
    tar xzf mafft-7.520-with-extensions-src.tgz && \
    cd mafft-7.520-with-extensions/core && \
    make clean && make && make install && \
    cd ../.. && rm -rf mafft-7.520-with-extensions*

# Instalar FastTree
RUN wget http://www.microbesonline.org/fasttree/FastTree -O /usr/local/bin/FastTree && \
    chmod +x /usr/local/bin/FastTree

# Instalar IQ-TREE
RUN wget https://github.com/iqtree/iqtree2/releases/download/v2.3.6/iqtree-2.3.6-Linux-intel.tar.gz && \
    tar xzf iqtree-2.3.6-Linux-intel.tar.gz && \
    cp iqtree-2.3.6-Linux-intel/bin/iqtree2 /usr/local/bin/iqtree && \
    rm -rf iqtree-2.3.6-Linux-intel*

# Criar diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do backend
COPY backend/ .

# Criar diretórios para uploads e resultados
RUN mkdir -p uploads results

# Expor porta
EXPOSE 8000

# Comando para iniciar o servidor
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
