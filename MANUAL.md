# Manual de operação

Como fazer as coisas no dia a dia: dar acesso pra uma aluna, acompanhar as
inscritas do Desafio, ajustar ponto, mexer no cupom e publicar mudanças.

Atualizado em 05/09/2026.

---

## 1. Onde fica cada coisa

| O quê | Endereço | Pra quê |
|---|---|---|
| **Painel do Desafio** | `thecreatorsclub.com.br/desafio/admin.html` | Acompanhar o desafio rodando: ranking, missões, comprovações, mural |
| **Admin** | `app.thecreatorsclub.com.br/admin/` | Painel técnico: alunas, códigos, cupons, e qualquer registro do sistema |
| **Cadastro do Dash** | `app.thecreatorsclub.com.br/signup/` | Onde a aluna cria a conta. Precisa de um código que você gera |
| **Entrada do Desafio** | `thecreatorsclub.com.br/desafio/login.html` | Link público pra divulgar. A participante se inscreve sozinha |
| **Vendas do Dash** | `thecreatorsclub.com.br/dashcreator/` | Landing e checkout, com o campo de cupom |

> **Dois cadastros diferentes, não confunda.**
> A **aluna do Dash** precisa de um código `TCC-...` que você gera.
> A **participante do Desafio** se cadastra sozinha e o sistema gera um
> código `DES-...` pra ela na hora.

---

## 2. Como você entra

O mesmo usuário e senha servem nos dois lugares: no painel do Desafio e no
admin. Usuário `admin`, senha a que você definiu.

- Durante a semana do desafio, use o **painel**: ele foi feito pra acompanhar
  a competição.
- Pro resto (alunas, códigos, cupons), use o **admin**.

### Esqueceu a senha

Não tem "esqueci minha senha", precisa trocar pelo servidor:

```bash
ssh dashcreator-coolify

# acha o container do app (o ID muda a cada deploy, sempre busque na hora)
APP=$(for c in $(docker ps -q); do docker inspect $c --format '{{json .Config.Labels}}' \
  | tr ',' '\n' | grep -q 'Host(`app.thecreatorsclub.com.br`)' && echo $c; done)

docker exec -it $APP /opt/venv/bin/python manage.py changepassword admin
```

Guarde esse bloco `APP=...`, ele aparece em várias seções aqui. Nunca anote o
ID do container: ele muda toda vez que o site publica.

---

## 3. Painel do Desafio

`thecreatorsclub.com.br/desafio/admin.html`

É a tela pra acompanhar o desafio enquanto ele acontece. Atualiza sozinha a
cada minuto, e tem um botão **Atualizar** se você não quiser esperar.

Em cima, seis números: inscritas, check-ins de hoje, missões entregues,
publicações, indicações e desativadas. Embaixo, cinco abas:

**Visão geral.** O ranking completo e um gráfico de movimento por dia, com
check-ins em azul e missões entregues em preto. É onde você vê se o
engajamento está subindo ou caindo.

**Participantes.** A lista toda, com busca por nome, email, Instagram ou
código. Cada linha mostra pontos, missões entregues, check-ins e por quem ela
foi indicada. Tem o botão **Copiar todos os emails**, pra disparo em massa.

**Missões.** As 7, com barra de progresso (quantas entregaram, quantas no
prazo, quantas comprovaram) e o campo de data. Mudou a data ali, vale na hora.

**Comprovações.** Tudo que as participantes enviaram, com o link já clicável,
e a marca de dentro ou fora do prazo. É a aba de conferir entrega.

**Mural.** Os posts e comentários da comunidade, com botão de remover em cada
um. Só use se precisar moderar.

### Lançar ou tirar pontos

Na aba Participantes, botão **Pontos** na linha da pessoa. Digite o número
(negativo pra tirar, tipo `-10`) e o motivo. O motivo fica registrado no
extrato dela junto com a data e a hora.

### Desativar alguém

Botão **Desativar** na mesma linha. Ela sai do ranking e não entra mais no
portal, mas os pontos e o histórico ficam guardados. Dá pra reativar depois.

---

## 4. Cadastrar uma aluna no Dash

A aluna cria a própria conta, mas só consegue com um código na mão.

**Passo 1.** Gere os códigos. O exemplo cria 2 de não pagante (permuta,
convidada, bolsa):

```bash
# no servidor, depois do ssh e do APP=...
docker exec $APP /opt/venv/bin/python manage.py generate_access_codes \
  --paid 0 --non-paid 2
```

`--paid` gera código de pagante, `--non-paid` de não pagante. O comando
imprime os códigos criados.

**Passo 2.** Veja os códigos livres em **STUDIO > Access codes**. Livre é o
que está com `assigned user` vazio e `is active` marcado. Copie um.

**Passo 3.** Mande pra aluna o código e o link `app.thecreatorsclub.com.br/signup/`

**Passo 4.** Confirme que ela entrou: volte em **Access codes** e procure o
código. Se `assigned user` agora tem o nome dela, o cadastro foi feito.

> **Um código serve uma pessoa só.** Depois de usado ele fica preso naquela
> conta. Se mandar o mesmo pra duas pessoas, a segunda recebe erro.

### Tirar o acesso de alguém

Em **Access codes**, abra o código e desmarque `is active`. Pra apagar a conta
de vez, vá em **Usuários** e remova o usuário.

---

## 5. Inscrições do Desafio Postaria Mais

Aqui você não gera nada. A participante entra pelo link, preenche nome, email
e WhatsApp, e o sistema devolve o código de acesso dela na tela e por email.

**Link pra divulgar:** `thecreatorsclub.com.br/desafio/login.html`

É esse link que vai no story, no direct, na bio. Sem senha, sem código, sem
depender de você.

### Se uma participante perder o código

Ela mesma resolve: na tela de entrada clica em **Entrar com meu código** e
depois em **Perdi meu código**, digita o email e o sistema reenvia. Se ela
insistir que não chegou, o código também está no painel, na aba
Participantes.

### Adicionar alguém na mão

Admin > **DESAFIO > Participantes > Adicionar**. Preencha nome e email, o
código é gerado sozinho ao salvar. Atenção: **por esse caminho o email não
sai**, então copie o código e mande pra pessoa junto com o link de entrada.

### Link de convite (indicações)

Cada participante tem um link próprio na aba **Indicações** do portal dela, no
formato `.../desafio/login.html?ref=DES-XXXXX`. Quem entra por ele fica
registrado como indicação dela, e aparece na coluna **Veio de** do painel.

> **Indicação ainda não vale ponto.** O briefing não definiu quantos, então
> por enquanto o sistema só registra a rede. Quando você decidir o valor, me
> fala que eu ligo a pontuação.

---

## 6. Pontuação e ranking

O sistema pontua sozinho, você não precisa aprovar nada.

| Ação da participante | Pontos | Regra |
|---|---:|---|
| Check-in do dia | 5 | Uma vez por dia, ao abrir o portal |
| Publicar na comunidade | 5 | Por publicação |
| Comentar no post de outra | 2 | Uma vez por post, e não vale no próprio |
| Concluir uma missão | 20 | Por missão |
| Concluir no dia da liberação | +10 | Bônus de prazo |
| Enviar a comprovação | +5 | Bônus por anexar link ou print |
| Sequência de 3 dias | +7 | Streak, dias seguidos com missão concluída |
| Sequência de 5 dias | +15 | Streak |
| Sequência de 7 dias | +50 | Streak |

Fazendo tudo, os 7 dias no prazo e com comprovação, uma participante chega
perto de **320 pontos**. Serve de régua pra calibrar prêmio.

### Ajustar pontos

O caminho fácil é o painel (seção 3). Se precisar do detalhe, o admin tem o
extrato completo em **DESAFIO > Ponto eventos**: cada linha é um crédito, com
quem ganhou, por qual motivo, quantos pontos e quando. É aqui que você
responde quando alguém reclamar que o ponto não entrou.

> **Por que existe o campo `referencia`.** É ele que impede o sistema de pagar
> o mesmo ponto duas vezes. Os ajustes que você faz pelo painel já vêm com uma
> referência única, então dois lançamentos iguais entram os dois.

---

## 7. As 7 missões

Uma missão libera por dia. Antes da data ela aparece bloqueada e ninguém
consegue concluir adiantado.

| Dia | Libera | Missão |
|---:|---|---|
| 01 | 14/09 | Arrumando a casa |
| 02 | 15/09 | Construção de Intenção |
| 03 | 16/09 | Construindo Conexão |
| 04 | 17/09 | Levantando Bandeiras |
| 05 | 18/09 | Condução dos seus processos |
| 06 | 19/09 | Atração Qualificada |
| 07 | 20/09 | A Grande Oferta |

### Adiar ou antecipar o desafio

No painel, aba **Missões**, mude o campo de data. Vale na hora, sem publicar
nada. (Pelo admin também dá: **DESAFIO > Missões**.)

> **Cuidado com o bônus de prazo.** Os 10 pontos de "no prazo" saem de quem
> concluiu no mesmo dia em que a missão liberou. Se mudar a data depois que o
> desafio começou, quem já concluiu mantém os pontos, mas a comparação muda
> daí pra frente.

### Mudar o texto de uma missão

O título fica no admin, mas o texto longo (o passo a passo que a participante
lê) mora na página. Isso é publicação de site, veja a seção 9.

---

## 8. Cupom do checkout

O cupom **ORGANIZADASH** já existe e já aparece no checkout do Dash, com **0%
de desconto**, esperando você decidir o valor.

1. Admin > **STUDIO > Coupons**
2. Na própria lista o campo **discount percent** é editável. Troque o `0` por
   `15` pra 15%, por exemplo
3. **Salvar** no fim da lista. Vale na hora, sem publicar nada

### Ligar e desligar

Na mesma lista tem a coluna **active**. Desmarcou, o cupom para de ser aceito
na hora. É assim que você encerra uma promoção sem apagar o histórico.

### Criar outro cupom

Botão **Adicionar**. Preencha o código (fica maiúsculo sozinho), o desconto, e
em `product key` escreva `dashcreator`. Esse campo diz em qual produto o cupom
funciona: se errar, o cupom existe mas nunca é aceito.

> **O desconto é calculado no servidor.** Ninguém consegue alterar o preço pelo
> navegador e pagar menos. O que a pessoa digita é só o código.

---

## 9. Publicar alterações

Dois caminhos, e eles não se misturam. O que muda é onde o arquivo mora.

### Caminho A: mudou algo do sistema

Pontuação, regras, admin, checkout, API do Desafio. É o app Django.

```bash
git push origin main
```

O Coolify vê o push e publica sozinho, já rodando as migrações. Leva alguns
minutos.

### Caminho B: mudou uma página do site

Landing do Dash, portal do Desafio, painel da organizadora, textos das
missões. São arquivos estáticos e **o push sozinho não sobe**, precisa copiar
na mão:

```bash
# exemplo com o portal do Desafio
scp -r landing/desafio/. dashcreator-coolify:/tmp/desafio-front/

ssh dashcreator-coolify

# acha o container do site (ID muda a cada publicação)
SITE=$(for c in $(docker ps -q); do docker inspect $c --format '{{json .Config.Labels}}' \
  | tr ',' '\n' | grep -q 'Host(`thecreatorsclub.com.br`)' && echo $c; done)

docker cp /tmp/desafio-front/. $SITE:/usr/share/nginx/html/desafio/
```

> **Se a mudança não aparecer no navegador,** é cache da Cloudflare. Entre no
> painel e faça **Purge Cache** do domínio.

---

## 10. Quando dá problema

### "Publiquei e nada mudou no ar"

Quase sempre é **disco cheio no servidor**: quando enche, o Coolify para de
publicar sem avisar.

```bash
# no servidor
df -h /

# se estiver perto de 100%:
docker builder prune -af
docker image prune -af
journalctl --vacuum-size=200M
```

Depois de limpar, faça o push de novo.

### "O painel abre mas não entra, ou dá erro ao carregar"

O painel é página estática falando com o app Django. Abra
`app.thecreatorsclub.com.br/desafio/api/ranking/` no navegador: se responder um
JSON, o problema é na página; se não abrir, o problema é o app.

### "Uma participante diz que fez e não pontuou"

Admin > **Ponto eventos**, filtre pelo nome dela. Você vê exatamente o que o
sistema registrou. Se o crédito não estiver lá e ela tiver razão, lance pelo
painel (seção 3).

### Coisas que nunca precisam de publicação

- Mudar o desconto ou desligar um cupom
- Mudar a data de liberação de uma missão
- Dar, tirar ou conferir pontos
- Desativar ou reativar uma participante
- Gerar código de acesso, desativar aluna

Tudo isso é painel ou admin e vale na hora. Publicação só entra quando muda
texto de página ou código.
