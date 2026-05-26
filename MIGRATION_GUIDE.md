# Migracao TreeApp: VPS Oracle -> Ubuntu 24 local

Este guia descreve uma migracao controlada para um novo Ubuntu 24 com IP publico, usando:
- Nginx no host (proxy e TLS)
- Backend em Docker com blue/green (deploy/deploy.sh)
- Certificados com Certbot (ver nota sobre Docker vs systemd)
- Frontend estatico em /opt/phylogentree/frontend/current

## 0) Pre-requisitos e decisoes

- Dominio: www.phylogentree.org (e opcionalmente phylogentree.org)
- Janela de corte: 1 hora
- Persistencia: /opt/phylogentree/shared/{uploads,results,data}
- Certificados: preferencia por Docker, mas Nginx esta no host

> Nota importante sobre Certbot em Docker
> O certbot em Docker deste repo foi feito para recarregar um Nginx em container.
> Como o Nginx aqui esta no host, a opcao mais simples e confiavel e usar Certbot no host via systemd.
> Se voce quiser insistir no certbot em container, precisara adaptar o deploy-hook para recarregar o Nginx do host.
> O passo a passo abaixo inclui as duas alternativas.

## Modo standby (copia pronta, sem colocar em producao)

Se voce quer apenas manter uma copia pronta no novo servidor e decidir mais tarde usar em producao, siga os passos abaixo em vez de fazer corte de DNS:

- Nao altere DNS no Porkbun e nao reduza TTL.
- Nao emita certificados agora. Ative o TLS so quando decidir expor o dominio.
- Mantenha as portas 80/443 fechadas no firewall (abra apenas para testes temporarios).
- Sincronize codigo e dados uma unica vez (snapshot) e mantenha congelado.
- Se precisar testar, use o IP direto ou um registro temporario em /etc/hosts no seu computador.

Quando decidir ir para producao, retome a partir das secoes de TLS/Certbot e Corte de DNS.

## 1) Inventario no servidor atual

1. Verifique versoes e servicos:

```bash
lsb_release -a
uname -a
docker --version
nginx -v
```

2. Identifique containers ativos:

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

3. Garanta a existencia do arquivo de ambiente:

```bash
sudo ls -la /opt/phylogentree/deploy/backend.env
```

4. Liste e meca os dados persistentes:

```bash
sudo du -sh /opt/phylogentree/shared/uploads
sudo du -sh /opt/phylogentree/shared/results
sudo du -sh /opt/phylogentree/shared/data
```

Resultado esperado: mapa claro de dados, variaveis de ambiente e tamanho total.

## 2) Planejamento de DNS no Porkbun

1. Reduza TTL de www.phylogentree.org (e phylogentree.org, se aplicavel) para 300s.
2. Aguarde a propagacao do TTL reduzido (pode levar algumas horas).
3. Defina a janela de corte de 1 hora.

Resultado esperado: propagacao mais rapida na troca de IP.

## 3) Preparar o novo Ubuntu 24

1. Criar usuario admin e configurar SSH:

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy
sudo mkdir -p /home/deploy/.ssh
sudo cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
sudo chown -R deploy:deploy /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys
```

2. Desabilitar login por senha (opcional, recomendado):

```bash
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload sshd
```

3. Atualizar pacotes e instalar dependencias:

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install ca-certificates curl gnupg lsb-release rsync ufw fail2ban nginx
```

4. Instalar Docker Engine e Compose (recomendado via repositorio oficial):

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker deploy
```

5. Refaça login do usuario deploy para aplicar o grupo docker.

Resultado esperado: host pronto para build e deploy.

## 4) Hardening basico (UFW + fail2ban)

1. UFW:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

2. fail2ban (jail simples para SSH):

```bash
sudo tee /etc/fail2ban/jail.d/sshd.conf > /dev/null <<'EOF'
[sshd]
enabled = true
maxretry = 5
bantime = 1h
findtime = 10m
EOF

sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
```

Resultado esperado: portas basicas abertas e brute-force mitigado.

## 5) Estrutura de diretorios no novo host

```bash
sudo mkdir -p /opt/phylogentree/deploy
sudo mkdir -p /opt/phylogentree/frontend/current
sudo mkdir -p /opt/phylogentree/shared/uploads
sudo mkdir -p /opt/phylogentree/shared/results
sudo mkdir -p /opt/phylogentree/shared/data
sudo chown -R deploy:deploy /opt/phylogentree
```

Resultado esperado: estrutura pronta para deploy e dados.

## 6) Configurar Nginx do host

1. Copie os arquivos de Nginx do repo para o host:

```bash
sudo cp /home/deploy/app/deploy/nginx/phylogentree.conf /etc/nginx/conf.d/phylogentree.conf
sudo cp /home/deploy/app/deploy/nginx/phylogentree_upstream.conf /etc/nginx/conf.d/phylogentree_upstream.conf
```

2. Verifique o server_name em phylogentree.conf (inclui www e raiz).

3. Teste e recarregue:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Resultado esperado: Nginx do host respondendo em 80/443 quando os certificados existirem.

## 7) TLS/Certbot (escolha a opcao)

### Opcao A (recomendada): Certbot no host com systemd

```bash
sudo apt -y install certbot
sudo certbot certonly --webroot -w /var/www/certbot -d phylogentree.org -d www.phylogentree.org
```

Crie a pasta de webroot usada pelo Nginx:

```bash
sudo mkdir -p /var/www/certbot
sudo chown -R www-data:www-data /var/www/certbot
```

Configure renovacao via systemd:

```bash
sudo cp /home/deploy/app/deploy/certbot/renew.service /etc/systemd/system/certbot-renew.service
sudo cp /home/deploy/app/deploy/certbot/renew.timer /etc/systemd/system/certbot-renew.timer
sudo systemctl daemon-reload
sudo systemctl enable --now certbot-renew.timer
```

### Opcao B: Certbot em Docker (requer ajuste)

Se voce mantiver Nginx no host, o certbot em Docker precisa de um deploy-hook que recarregue o Nginx do host.
A versao atual do repo assume Nginx em container. Para usar em host, faca:

1. Crie um hook simples no host:

```bash
sudo tee /usr/local/bin/reload-nginx-host.sh > /dev/null <<'EOF'
#!/bin/sh
set -e
nginx -t && systemctl reload nginx
EOF
sudo chmod +x /usr/local/bin/reload-nginx-host.sh
```

2. Execute certbot em container apontando o hook:

```bash
docker run --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/www/certbot:/var/www/certbot \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d phylogentree.org -d www.phylogentree.org \
  --deploy-hook /usr/local/bin/reload-nginx-host.sh
```

Para renovacao automatica, considere cron no host chamando o container.

Resultado esperado: HTTPS ativo e renovacao automatica configurada.

## 8) Sincronizar codigo para o novo servidor

A partir da sua maquina local (repo):

```bash
cd /home/genivaldo/fomitiporia_org_treeapp-main

# Ajuste host e usuario conforme o novo servidor
REMOTE_USER=deploy REMOTE_HOST=SEU_IP_PUBLICO REMOTE_BASE=/home/deploy/app ./deploy/sync.sh --deploy
REMOTE_USER=deploy REMOTE_HOST=SEU_IP_PUBLICO ./deploy/sync.sh --frontend
```

Resultado esperado: deploy e frontend em /home/deploy/app e /opt/phylogentree/frontend/current.

## 9) Migrar dados persistentes

1. Primeira sincronizacao (sem corte):

```bash
rsync -avz --delete \
  ubuntu@ORIGEM:/opt/phylogentree/shared/ \
  deploy@SEU_IP_PUBLICO:/opt/phylogentree/shared/
```

2. Segunda sincronizacao (durante a janela de corte):

```bash
rsync -avz --delete \
  ubuntu@ORIGEM:/opt/phylogentree/shared/ \
  deploy@SEU_IP_PUBLICO:/opt/phylogentree/shared/
```

Resultado esperado: dados atualizados e consistentes.

## 10) Configurar backend.env

Crie o arquivo no novo host com as mesmas variaveis do servidor antigo:

```bash
sudo tee /opt/phylogentree/deploy/backend.env > /dev/null <<'EOF'
# Copie aqui as variaveis do servidor antigo
# Exemplo:
# PUBLIC_BASE_URL=https://phylogentree.org
# JOB_RETENTION_DAYS=3
EOF
```

Resultado esperado: backend com as mesmas configuracoes.

## 11) Deploy do backend (blue/green)

1. No novo host, acesse o repo sincronizado:

```bash
cd /home/deploy/app/deploy
```

2. Se for primeira vez ou houve mudanca de dependencias:

```bash
./deploy.sh 1 --build-base --build-app --base-tag 2026-04
```

3. Para deploys normais:

```bash
./deploy.sh 2 --build-app --base-tag 2026-04
```

4. Verifique status:

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

Resultado esperado: backend respondendo em 127.0.0.1:9001 ou 9002 e Nginx apontando para o upstream ativo.

## 12) Validacao funcional

1. Teste local no novo host:

```bash
curl -I http://127.0.0.1:9001/
```

2. Teste via Nginx:

```bash
curl -I https://www.phylogentree.org/api/
```

3. Teste o frontend no navegador e um fluxo de upload.

Resultado esperado: frontend ok, API ok, dados acessiveis.

## 13) Corte de DNS (janela de 1 hora)

1. Congelar escrita no servidor antigo (se aplicavel).
2. Rodar rsync final (passo 9).
3. Atualizar registros A/AAAA no Porkbun para o novo IP.
4. Monitorar propagacao:

```bash
dig +short www.phylogentree.org
dig +short phylogentree.org
```

Resultado esperado: usuarios acessando o novo servidor.

## 14) Pos-corte e rollback

- Monitorar logs:

```bash
sudo journalctl -u nginx -f
```

- Ajustar fail2ban se necessario.
- Manter a VPS antiga por alguns dias para rollback rapido.

## Checklist final

- [ ] SSH com chave e senha desativada
- [ ] UFW ativo com 22/80/443
- [ ] fail2ban ativo no sshd
- [ ] Nginx valida e responde em 80/443
- [ ] Certificados validos e renovacao ativa
- [ ] Backend respondendo via /api/
- [ ] Frontend carregando e funcional
- [ ] DNS apontando para o novo IP
