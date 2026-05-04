# 1) Visão geral do disco
df -h
df -i

# 2) Quais pastas do / estão grandes (mesmo filesystem)
sudo du -xhd1 / | sort -h

# 3) Foco no /var (geralmente onde cresce)
sudo du -xhd1 /var | sort -h

# 4) Uso detalhado do Docker
docker system df -v

# 5) Tamanho dentro do storage do Docker
sudo du -xhd1 /var/lib/docker | sort -h
sudo du -xhd1 /var/lib/docker/overlay2 | sort -h | tail
sudo du -xhd1 /var/lib/docker/volumes | sort -h | tail

-------------------------------------------------------------
# Logs do systemd
journalctl --disk-usage

# Maiores logs de container
sudo find /var/lib/docker/containers -name "*-json.log" -printf "%s %p\n" | sort -nr | head -20
-------------------------------------------------------------
# remove imagens dangling + build cache não usado
docker image prune -a
docker builder prune -a

# remove tudo que não está em uso (containers parados, redes, imagens sem uso, cache)
docker system prune -a

# só se tiver certeza que volumes órfãos podem sair
docker volume prune
-------------------------------------------------------------
echo "== /var/lib (subpastas) =="
sudo du -xhd1 /var/lib | sort -h

echo
echo "== /var/lib/docker (subpastas) =="
sudo du -xhd1 /var/lib/docker | sort -h

echo
echo "== Docker detalhado =="
docker system df -v

echo
echo "== Maiores arquivos em /var (>=200MB) =="
sudo find /var -xdev -type f -size +200M -printf '%12s  %p\n' | sort -nr | head -20

echo
echo "== Logs docker json (top 20) =="
sudo find /var/lib/docker/containers -name '*-json.log' -printf '%12s  %p\n' | sort -nr | head -20

echo
echo "== Uso do journalctl =="
journalctl --disk-usage
-------------------------------------------------------------
## Limpeza segura depois da auditoria:

# Não afeta containers em execução
docker container prune -f
docker image prune -a -f
docker builder prune -a -f

# Só remove volumes não usados por nenhum container
docker volume prune -f

# Limita logs do systemd (ajuste conforme sua necessidade)
sudo journalctl --vacuum-time=7d
-------------------------------------------------------------
O que está ocupando no seu servidor:

/var/lib/containerd = 22G (principal vilão)
Build cache do Docker = 16.95G (confirmado no docker system df -v)
Logs do systemd journal = 1.0G
Logs JSON de containers = pequenos (menos de 1MB cada, irrelevantes aqui)
Ou seja: o ganho pequeno ao remover imagens foi esperado, porque o grosso está em cache/blobs do containerd.

Ordem segura para limpar com maior impacto:

Limpar cache de build (maior ganho, não derruba containers em execução)
$ docker builder prune -a -f
# Alternativa mais conservadora:
# docker builder prune -f --filter until=168h

Limpar objetos Docker não usados
$ docker system prune -a -f

Limpar volumes órfãos (somente os sem uso)
$ docker volume prune -f

Reduzir journal (logs do sistema)
$ sudo journalctl --vacuum-time=7d
ou por tamanho:
$ sudo journalctl --vacuum-size=200M

Depois valide:
$ df -h /
$ docker system df -v
$ sudo du -xhd1 /var/lib | sort -h
$ sudo du -xhd1 /var | sort -h
-------------------------------------------------------------
