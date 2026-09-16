# The Creators Club Landing

Arquivos estaticos do dominio `thecreatorsclub.com.br` (home, Dash Creator, Planner,
checkouts, Creator Day, Desafio Postaria Mais, metricas).

## Como publica

Desde 16/09/2026 o site sai pelo git: `git push origin main` e o Coolify publica
sozinho (junto com o app Django).

- Resource do Coolify: `pagina_incial_landing`, Build Pack `Static`, Base Directory
  `/landing`, deploy automatico ligado.
- Dominios: `https://thecreatorsclub.com.br,https://www.thecreatorsclub.com.br`.
- So vai pro ar o que esta no git. Arquivo copiado direto no container some no
  proximo deploy.

## Nginx

A configuracao mora em `nginx-default.conf` e tambem fica salva no Coolify, no
campo "Custom Nginx Configuration" do resource. O Coolify guarda esse campo em
base64: altere pela tela do Coolify (que codifica sozinha), nunca gravando texto
puro direto no banco, senao o nginx nao sobe.

O dashboard continua em outro resource no Coolify, usando o mesmo repositorio e o
dominio `https://app.thecreatorsclub.com.br`.
