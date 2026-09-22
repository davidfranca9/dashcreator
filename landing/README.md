# The Creators Club Landing

Arquivos estaticos do dominio `thecreatorsclub.com.br` (home, Dash Creator, Planner,
checkouts, Creator Day, Desafio Postaria Mais, metricas).

## Mentoria HPC (`/hpc/`)

A pasta `hpc/` e gerada, nao se edita a mao. O codigo fica em
`high-performance-creator/` (projeto do Lovable, TanStack Start). Para atualizar:

```sh
cd high-performance-creator
MSYS_NO_PATHCONV=1 HPC_BASE=/hpc/ npm run build   # no Git Bash; no PowerShell: $env:HPC_BASE="/hpc/"; npm run build
rm -rf ../landing/hpc && cp -r dist/client ../landing/hpc && rm -f ../landing/hpc/robots.txt
```

O botao da oferta leva ao checkout proprio em `/checkout/hpc/` (produto `hpc` no app).

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
