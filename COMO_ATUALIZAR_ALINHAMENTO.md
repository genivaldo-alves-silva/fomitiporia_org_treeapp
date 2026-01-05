# Como Atualizar a Matriz de Alinhamento Padrão

## 📄 Arquivo: `backend/default_alignment.fasta`

Este arquivo contém o alinhamento padrão usado quando o usuário não faz upload de uma matriz própria.

## 🔄 Como Atualizar

### Método 1: Edição Direta (Mais Simples)
1. Abra o arquivo `backend/default_alignment.fasta` no VS Code
2. Cole suas sequências alinhadas em formato FASTA
3. Salve o arquivo (Ctrl+S)
4. Pronto! A próxima análise já usará o novo alinhamento

### Método 2: Substituir Arquivo
```bash
# Copiar seu arquivo para substituir o padrão
cp /caminho/para/seu_alinhamento.fas backend/default_alignment.fasta
```

### Método 3: Via SCP (Servidor Remoto)
```bash
scp seu_alinhamento_atualizado.fas usuario@servidor:/caminho/backend/default_alignment.fasta
```

## ✅ Formato do Arquivo

O arquivo deve estar em formato FASTA padrão:

```fasta
>sequencia_1
ATCGATCGATCGATCG---AAATTTGGGCCC
>sequencia_2
ATCGATCGATCGATCG---AAATTTGGGCCC
>sequencia_3
ATCGATCGATCGATCGGGGAAATTTGGGCCC
```

**Importante:**
- Todas as sequências devem ter o **mesmo comprimento** (alinhadas)
- Use `-` para representar gaps
- Uma linha `>nome` seguida da sequência

## 🚀 Não Precisa Reiniciar!

O servidor lê o arquivo a cada nova análise, então:
- ✅ Edite quando quiser
- ✅ Não precisa reiniciar o backend
- ✅ Próxima análise já usa o novo arquivo

## 📊 Verificar o Arquivo Atual

```bash
# Ver primeiras linhas
head -n 20 backend/default_alignment.fasta

# Contar sequências
grep -c "^>" backend/default_alignment.fasta

# Ver tamanho das sequências (primeira sequência)
grep -v "^>" backend/default_alignment.fasta | head -n 1 | wc -c
```

## 🔍 Exemplo de Atualização Completa

```bash
# 1. Fazer backup do atual
cp backend/default_alignment.fasta backend/default_alignment.fasta.backup

# 2. Copiar novo alinhamento
cp meu_novo_alinhamento.fas backend/default_alignment.fasta

# 3. Verificar
head backend/default_alignment.fasta
```

---

**Dica:** Mantenha backups dos alinhamentos anteriores com data:
```bash
cp backend/default_alignment.fasta backups/alignment_$(date +%Y%m%d).fasta
```
