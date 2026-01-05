#!/bin/bash
# Script para instalar ferramentas de bioinformática localmente

set -e  # Parar se houver erro

echo "🔬 Instalando ferramentas de bioinformática..."

# Atualizar repositórios
echo "📦 Atualizando apt..."
sudo apt-get update -qq

# 1. MAFFT (disponível no apt)
echo "✅ Instalando MAFFT..."
sudo apt-get install -y mafft

# 2. FastTree
echo "✅ Instalando FastTree..."
sudo apt-get install -y fasttree

# 3. IQ-TREE (precisa baixar binário)
echo "✅ Instalando IQ-TREE..."
cd /tmp
wget -q https://github.com/iqtree/iqtree2/releases/download/v2.3.6/iqtree-2.3.6-Linux-intel.tar.gz
tar xzf iqtree-2.3.6-Linux-intel.tar.gz
sudo cp iqtree-2.3.6-Linux-intel/bin/iqtree2 /usr/local/bin/iqtree
sudo chmod +x /usr/local/bin/iqtree
rm -rf iqtree-2.3.6-Linux-intel*

echo ""
echo "✅ Instalação concluída!"
echo ""
echo "Verificando versões:"
echo "  - MAFFT: $(mafft --version 2>&1 | head -n1)"
echo "  - FastTree: $(fasttree -expert 2>&1 | head -n1 || echo 'instalado')"
echo "  - IQ-TREE: $(iqtree --version | head -n1)"
echo ""
echo "🚀 Agora você pode iniciar o backend!"
