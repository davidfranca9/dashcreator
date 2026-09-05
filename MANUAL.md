# Manual de operação

Como fazer as coisas no dia a dia: dar acesso pra uma aluna, acompanhar as
inscritas do Desafio, ajustar ponto, mexer no cupom e publicar mudanças.

Atualizado em 05/09/2026.

---

## 1. Onde fica cada coisa

| O quê | Endereço | Pra quê |
|---|---|---|
| **Admin** | `app.thecreatorsclub.com.br/admin/` | Seu painel: alunas, códigos, cupons, inscritas do Desafio, pontos |
| **Cadastro do Dash** | `app.thecreatorsclub.com.br/signup/` | Onde a aluna cria a conta. Precisa de um código que você gera |
| **Entrada do Desafio** | `thecreatorsclub.com.br/desafio/login.html` | Link público pra divulgar. A participante se inscreve sozinha |
| **Vendas do Dash** | `thecreatorsclub.com.br/dashcreator/` | Landing e checkout, com o campo de cupom |

> **Dois cadastros diferentes, não confunda.**
> A **aluna do Dash** precisa de um código `TCC-...` que você gera.
> A **participante do Desafio** se cadastra sozinha e o sistema gera um
> código `DES-...` pra ela na hora.

---

## 2. Como você entra

1. Abra `app.thecreatorsclub.com.br/admin/`
2. Usuário `admin`, senha a que você definiu
3. Dentro tem dois blocos: **STUDIO** (Dash, alunas, códigos, cupons,
   financeiro) e **DESAFIO** (participantes, missões, pontos, comunidade)

### Esqueceu a senha

Não tem "esqueci minha senha" no admin, precisa trocar pelo servidor:

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

## 3. Cadastrar uma aluna no Dash

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

## 4. Inscrições do Desafio Postaria Mais

Aqui você não gera nada. A participante entra pelo link, preenche nome, email
e WhatsApp, e o sistema devolve o código de acesso dela na tela e por email.

**Link pra divulgar:** `thecreatorsclub.com.br/desafio/login.html`

É esse link que vai no story, no direct, na bio. Sem senha, sem código, sem
depender de você.

### Acompanhar quem se inscreveu

Admin > **DESAFIO > Participantes**. Mostra nome, email, WhatsApp, Instagram,
o código dela, o total de pontos e a data de inscrição. Clicando no cabeçalho
da coluna **Pontos** você ordena por pontuação: esse é o seu ranking.

### Se uma participante perder o código

Ela mesma resolve: na tela de entrada clica em **Entrar com meu código** e
depois em **Perdi meu código**, digita o email e o sistema reenvia. Se ela
insistir que não chegou, o código também está visível em **Participantes**.

### Link de convite (indicações)

Cada participante tem um link próprio na aba **Indicações** do portal dela, no
formato `.../desafio/login.html?ref=DES-XXXXX`. Quem entra por ele fica
registrado como indicação dela.

> **Indicação ainda não vale ponto.** O briefing não definiu quantos, então
> por enquanto o sistema só registra a rede. Quando você decidir o valor, me
> fala que eu ligo a pontuação.

---

## 5. Pontuação e ranking

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

### Conferir de onde veio cada ponto

Admin > **DESAFIO > Ponto eventos**. Cada linha é um crédito: quem ganhou, por
qual motivo, quantos pontos e quando. É aqui que você responde quando alguém
reclamar que o ponto não entrou.

### Dar ou tirar ponto na mão

- **Dar:** em **Ponto eventos** clique em **Adicionar**, escolha a
  participante, o tipo, os pontos, e escreva qualquer coisa em `referencia`
  (por exemplo `ajuste-manual-05-09`).
- **Tirar:** apague a linha, ou crie uma nova com pontos negativos se quiser
  deixar o rastro do ajuste.

O total e o ranking são a soma dessas linhas, então o ajuste reflete na hora
no portal da participante.

> **Por que existe o campo `referencia`.** É ele que impede o sistema de pagar
> o mesmo ponto duas vezes. Num ajuste manual, use um texto que você não vá
> repetir, senão o segundo ajuste igual não entra.

---

## 6. As 7 missões

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

Admin > **DESAFIO > Missões**. Abra a missão e mude `data liberacao`. Vale na
hora, sem publicar nada.

> **Cuidado com o bônus de prazo.** Os 10 pontos de "no prazo" saem de quem
> concluiu no mesmo dia em que a missão liberou. Se mudar a data depois que o
> desafio começou, quem já concluiu mantém os pontos, mas a comparação muda
> daí pra frente.

### Mudar o texto de uma missão

O título fica no admin, mas o texto longo (o passo a passo que a participante
lê) mora na página. Isso é publicação de site, veja a seção 8.

---

## 7. Cupom do checkout

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

## 8. Publicar alterações

Dois caminhos, e eles não se misturam. O que muda é onde o arquivo mora.

### Caminho A: mudou algo do sistema

Pontuação, regras, admin, checkout, API do Desafio. É o app Django.

```bash
git push origin main
```

O Coolify vê o push e publica sozinho, já rodando as migrações. Leva alguns
minutos.

### Caminho B: mudou uma página do site

Landing do Dash, portal do Desafio, textos das missões. São arquivos estáticos
e **o push sozinho não sobe**, precisa copiar na mão:

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

## 9. Quando dá problema

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

### "O site abre mas o portal do Desafio dá erro"

O portal é página estática falando com o app Django. Abra
`app.thecreatorsclub.com.br/desafio/api/ranking/` no navegador: se responder um
JSON, o problema é na página; se não abrir, o problema é o app.

### "Uma participante diz que fez e não pontuou"

Admin > **Ponto eventos**, filtre pelo nome dela. Você vê exatamente o que o
sistema registrou. Se o crédito não estiver lá e ela tiver razão, lance na mão
(seção 5).

### Coisas que nunca precisam de publicação

- Mudar o desconto ou desligar um cupom
- Mudar a data de liberação de uma missão
- Dar, tirar ou conferir pontos
- Gerar código de acesso, desativar aluna

Tudo isso é admin e vale na hora. Publicação só entra quando muda texto de
página ou código.
