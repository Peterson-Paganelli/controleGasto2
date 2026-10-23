# Controle de Gasto Pessoal (CGP)

Estrutura inicial da sprint 1: React com TypeScript, API FastAPI e PostgreSQL.

## Como iniciar

1. Instale o Docker Desktop e deixe-o aberto.
2. Na pasta do projeto, execute:

   ```sh
   docker compose up --build
   ```

Abra o frontend em <http://localhost:5173>. A API fica em <http://localhost:8000> e sua documentação em <http://localhost:8000/docs>. Para conferir se o backend responde, abra <http://localhost:8000/health>; a resposta esperada é `{"status":"ok"}`.

Para parar os serviços, pressione `Ctrl+C` e execute `docker compose down`. Os dados do PostgreSQL continuam salvos no volume `postgres_data`.

## Organização

- `frontend/`: interface React e TypeScript.
- `backend/app/`: API FastAPI.
- `compose.yaml`: inicialização dos três serviços.
- `.env.example`: valores que podem ser personalizados em um arquivo `.env`. Os padrões do Compose são apenas para desenvolvimento local; `.env` não entra no Git.

As mudanças em `frontend/src/` e `backend/app/` são recarregadas automaticamente. Ao alterar dependências ou arquivos de configuração, execute `docker compose up --build` novamente.

A API se conecta ao PostgreSQL e aplica as migrations automaticamente na inicialização.
`/health` verifica também a conexão com o banco e retorna HTTP 503 se ele estiver indisponível.

## Banco de dados

- `dados_pessoal`: ID, nome, CPF, telefone, e-mail e hash da senha. CPF, telefone e e-mail são únicos.
- `tabela_gastos`: ID, usuário, valor, data e descrição. A chave estrangeira vincula o gasto ao usuário.
- `schema_migrations`: registra as migrations já aplicadas.
- `sessoes`: sessões ativas, criadas no login e removidas no logout (migration `002_sessoes.sql`).
- `p_criacaodeconta`: cadastra o usuário, normaliza o e-mail e gera o hash bcrypt com `pgcrypto`.
- `validador_senhaeemail`: retorna `true` ou `false` ao verificar as credenciais.
- `p_adicaotabelagastos`: adiciona um gasto.
- `p_excluirtabelagastos`: exclui um gasto somente quando o ID do usuário corresponde ao dono.

Os valores usam `numeric(14, 2)` e devem ser positivos. Os campos são obrigatórios;
o CPF deve ter 11 dígitos, sem pontuação. As senhas devem ter entre 1 e 72 bytes
(limite do bcrypt; caracteres acentuados podem ocupar mais de um byte).

Para aplicar a estrutura, inclusive em um volume PostgreSQL existente:

```sh
docker compose up -d --build db backend
```

A migration é executada em uma transação e registrada uma única vez. Reiniciar a API
não recria as tabelas nem apaga dados. Para mudanças futuras, adicione outro arquivo
SQL numerado em `backend/migrations/`, sem editar migrations já aplicadas.

O backup e os cadastros de exemplo do ZIP não são importados. As rotinas estão
disponíveis no banco. Os endpoints de cadastro (`POST /cadastro`) e login (`POST /login`) já estão implementados;
As telas de cadastro e login estão integradas. Os endpoints de gastos estão disponíveis
como recurso de teste de isolamento (S1-06), ainda sem interface de gastos.
As rotinas usam `dados_pessoal`. Tabelas de versões anteriores, como `users` e
`alembic_version`, são preservadas caso existam no volume, mas não são sincronizadas
com a nova estrutura.

Exemplo para executar com `docker compose exec db psql -U cgp -d cgp`
(ajuste usuário e banco se personalizou o `.env`):

```sql
BEGIN;
CALL p_criacaodeconta('Usuário de teste', '12345678901', '47900000001',
                     'teste@example.com', 'senha-de-teste');
SELECT validador_senhaeemail('TESTE@EXAMPLE.COM', 'senha-de-teste');
SELECT id_dadopessoal, nome, email FROM dados_pessoal;
-- Use o ID retornado na chamada abaixo.
-- CALL p_adicaotabelagastos(1, 19.90, CURRENT_DATE, 'Almoço');
ROLLBACK;
```

## Cadastro (S1-03)

`POST /cadastro` recebe JSON com `nome`, `cpf`, `telefone`, `email` e `senha`, gera
o hash pelo componente `gerar_hash` de S1-04 (bcrypt com custo 12) e salva o usuário.

Validações: nome obrigatório; CPF com 11 dígitos (pontos e traço são removidos);
telefone com 10 a 13 dígitos; e-mail válido (normalizado em minúsculas); senha com
no mínimo 8 caracteres e no máximo 72 bytes.

Respostas:

- `201` com `{"id", "nome", "email"}` (nunca a senha nem o hash);
- `422` para dados inválidos;
- `409` para e-mail, CPF ou telefone já cadastrados.

Os erros vêm no formato `{"detail": [{"campo": "email", "mensagem": "E-mail já cadastrado."}]}`.

```sh
curl -X POST http://localhost:8000/cadastro -H "Content-Type: application/json" \
  -d '{"nome":"Maria","cpf":"12345678901","telefone":"47900000001","email":"maria@example.com","senha":"senha-de-teste"}'
```

## Senhas com BCrypt (S1-04)

`backend/app/senhas.py` oferece `gerar_hash(senha)`, `verificar_senha(senha, hash)` e
`custo_do_hash(hash)`. O cálculo usa o pgcrypto do PostgreSQL, o mesmo das procedures
`p_criacaodeconta` e `validador_senhaeemail`, com custo 12 por padrão. Custo abaixo de 10
é recusado, e senhas devem ter de 1 a 72 bytes. O banco também impede gravar senha em
texto puro: a coluna `dados_pessoal.senha` só aceita hashes BCrypt.

## Login e rotas protegidas (S1-05)

`POST /login` recebe `email` e `senha` em JSON, verifica a senha pelo componente
BCrypt e retorna `{"access_token": "...", "token_type": "bearer"}`.
E-mail ou senha incorretos retornam `401` com a mensagem `E-mail ou senha inválidos.`.

O token JWT vale por 30 minutos. Envie `Authorization: Bearer <access_token>`
para acessar `GET /me`, que retorna apenas `id`, `nome` e `email` do usuário autenticado.
Token ausente, inválido, expirado ou de usuário removido retorna `401`.
Para proteger novas rotas, use `Depends(usuario_autenticado)` de `app.auth`.

```sh
curl -X POST http://localhost:8000/login -H "Content-Type: application/json" \
  -d '{"email":"maria@example.com","senha":"senha-de-teste"}'
curl http://localhost:8000/me -H "Authorization: Bearer <access_token>"
```

Configure `JWT_SECRET` no `.env` com uma chave aleatória de pelo menos 32 bytes
para manter os tokens após reiniciar e compartilhar a chave entre instâncias.
Você pode gerar uma com `python -c "import secrets; print(secrets.token_hex(32))"`.
Sem essa variável, a API gera uma chave temporária a cada inicialização.

## Isolamento de dados por usuário (S1-06)

`/gastos` é o recurso usado nesta sprint para aplicar a identidade autenticada às
consultas e operações financeiras. Todas as rotas exigem `Authorization: Bearer <access_token>`;
sem token válido a resposta é `401`.

- `GET /gastos`: lista os gastos do usuário autenticado.
- `POST /gastos`: cria um gasto (`valor`, `data` e `descricao`). O dono é sempre o usuário do token.
- `GET /gastos/{id}`: visualiza um gasto.
- `PUT /gastos/{id}`: altera um gasto.
- `DELETE /gastos/{id}`: exclui um gasto (`204`).

O `valor` é um número positivo com no máximo 2 casas decimais e é devolvido como texto
(`"19.90"`). A `data` usa o formato `AAAA-MM-DD`.

O isolamento é feito nas próprias consultas SQL, que sempre filtram por
`id_dadospessoal` do usuário do token. Se o usuário A tentar acessar, alterar ou excluir
um registro do usuário B, a API responde `404` (a mesma resposta de um registro inexistente),
sem revelar que o registro existe. O dono nunca é lido do corpo nem da URL.

Para novos recursos com dados por usuário, adicione as rotas ao router (ou use
`Depends(usuario_autenticado)`) e filtre toda consulta pelo ID do usuário autenticado.

`tests/test_gastos_isolamento.py` valida o isolamento com dois usuários, usando banco e
autenticação reais (execute pelo comando de testes abaixo, no banco `cgp_test`).

## Formulários de cadastro e login (S1-07)

Em `http://localhost:5173`, use **Criar conta** para cadastrar nome, CPF, telefone,
e-mail e senha. Após o cadastro, a tela pede o login e mantém o e-mail preenchido.
Ao entrar, a interface consulta `/me` com o token e mostra o nome e o e-mail da conta.
O botão **Sair da conta** encerra a sessão na API e retorna ao login.

Os campos obrigatórios, e-mail, CPF, telefone e tamanho da senha são validados.
Erros de cadastro, credenciais e conexão aparecem na tela, sem mostrar respostas
internas, senha, hash ou token. O token fica apenas na memória: recarregar a página
exige um novo login.

As chamadas usam `/api`, encaminhado pelo proxy do Vite para o backend. No Docker,
`API_URL` já aponta para `http://backend:8000`. Fora do Docker, o padrão é
`http://localhost:8000`; rode o frontend com `pnpm install` e `pnpm dev` dentro de
`frontend/` (ou os comandos equivalentes do npm).
Para conferir o frontend, execute `pnpm test` e `pnpm build` nessa pasta.
Os testes da comunicação com a API usam respostas simuladas.

## Área interna e logout (S1-08)

O frontend tem as rotas `/login`, `/cadastro` e `/app`. A área interna em `/app`
mostra a identificação da conta e uma navegação inicial. Visitantes são direcionados
ao login. Antes de exibir os dados, a interface confirma a sessão em `/me`.

`POST /logout`, com `Authorization: Bearer <access_token>`, remove a sessão do
banco e retorna `204`, sem corpo. O token dessa sessão passa a ser rejeitado com
`401`, mesmo que ainda não tenha expirado. Outros logins da mesma conta continuam
válidos. Cada token contém um identificador de sessão (`jti`).

Após sair, abrir `/app` ou usar o botão Voltar não libera a área interna.
O token continua apenas na memória; recarregar a página exige novo login.
Se a API falhar durante o logout, a interface informa o erro e permite tentar
novamente, sem indicar que a sessão foi encerrada.

## Responsividade (S1-09)

As telas de cadastro, login e área interna funcionam de 360 px (celular) até desktop:

- **Celular (até 480 px):** uma coluna, botões na largura toda e margens menores.
- **Tablet (768 px ou mais):** mais espaço interno nos cartões.
- **Desktop (900 px ou mais):** a área interna usa duas colunas (boas-vindas e dados da conta).
- Campos, botões e o link do menu têm no mínimo 44 px de altura para facilitar o toque.
- Nomes e e-mails longos quebram linha em vez de estourar a tela, e não há rolagem horizontal.
- Os tamanhos usam `rem`, então o layout também se mantém com o texto ampliado no navegador.

Para conferir manualmente, abra `http://localhost:5173`, pressione F12 e ative o modo de
dispositivo (Ctrl+Shift+M). Teste as três telas em 360 px, 768 px e em tela cheia: não deve
aparecer barra de rolagem horizontal, e todos os campos e botões devem estar visíveis.
Repita ampliando o texto do navegador (Ctrl e +) até 200%.

## Testes de autenticação e segurança (S1-10)

`backend/tests/test_integracao_seguranca.py` testa a API de verdade (TestClient) com o
PostgreSQL de teste, sem simular banco nem senhas. Cobertura por critério do card:

| Critério | Onde é testado |
| --- | --- |
| Cadastro duplicado é rejeitado | `test_cadastro_duplicado_e_rejeitado` (e-mail, CPF e telefone, com `409`) |
| Senha incorreta é rejeitada | `test_senha_incorreta_e_rejeitada_sem_revelar_se_o_email_existe` |
| BCrypt | `test_senha_e_gravada_somente_como_hash_bcrypt_com_custo_minimo` e `test_senhas.py` |
| Acesso sem autenticação | `test_toda_rota_exige_autenticacao_exceto_as_publicas` |
| Acesso a dados de outro usuário | `test_acesso_aos_dados_de_outro_usuario_e_rejeitado` e `test_gastos_isolamento.py` |

Também verificam: tokens adulterados, assinados com outra chave, com algoritmo `none` ou de
outra sessão; sessão expirada e usuário removido; logout; senha de 73 bytes não aceita por
truncamento do bcrypt; textos com SQL tratados como dados; e respostas e erros que nunca
repetem a senha nem o hash.

`test_toda_rota_exige_autenticacao_exceto_as_publicas` percorre todas as rotas da API,
incluindo routers aninhados e seus prefixos, com `iter_route_contexts`. Se você
criar uma rota nova sem `Depends(usuario_autenticado)`, ele falha. Rotas públicas de
propósito precisam ser listadas em `ROTAS_PUBLICAS` no próprio teste.

Para executar todos os testes do backend (inclui os desta seção):

```sh
docker compose run --rm -e POSTGRES_DB=cgp_test backend python -m unittest discover -s tests -v
```

Ainda não existe e, portanto, não é testado: limite de tentativas de login (proteção contra
força bruta) e renovação de token.

## Testes do banco

Os testes usam um banco separado com nome terminado em `_test` e removem os
cadastros e gastos criados ao fim de cada teste. Com os serviços iniciados e os valores
padrão de desenvolvimento:

```sh
docker compose exec db createdb -U cgp cgp_test
docker compose run --rm -e POSTGRES_DB=cgp_test backend python -m unittest discover -s tests -v
```

Crie `cgp_test` apenas na primeira execução. Os testes verificam reaplicação das
migrations, cadastro (banco e endpoint), hash BCrypt e validação de senha, unicidade, chave estrangeira,
valores monetários, exclusão por dono e saúde da conexão.
Os testes HTTP de login usam banco simulado e podem rodar sem PostgreSQL:
`python -m unittest discover -s tests -p test_login.py -v` (dentro de `backend/`,
com as dependências de `requirements.txt` instaladas).

## Sprint 1

A validação integrada do item S1-11, seus resultados e os comandos para executar
os serviços e testes E2E estão em [VALIDACAO_SPRINT_1.md](VALIDACAO_SPRINT_1.md).

As tarefas estão em [KANBAN_SPRINT_1.md](KANBAN_SPRINT_1.md) e no [quadro Trello](https://trello.com/b/EQFx2d39/controle-de-gasto-pessoal-cgp).
