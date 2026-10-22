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

A estrutura foi adaptada dos scripts de `BD_EngSowt_Trabalho.zip` e está versionada em
`backend/migrations/001_usuarios_e_gastos.sql`:

- `dados_pessoal`: ID, nome, CPF, telefone, e-mail e hash da senha. CPF, telefone e e-mail são únicos.
- `tabela_gastos`: ID, usuário, valor, data e descrição. A chave estrangeira vincula o gasto ao usuário.
- `schema_migrations`: registra as migrations já aplicadas.
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
disponíveis no banco. O endpoint de cadastro (`POST /cadastro`) já está implementado;
telas, login e endpoints de gastos ainda não.
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

## Sprint 1

As tarefas estão em [KANBAN_SPRINT_1.md](KANBAN_SPRINT_1.md) e no [quadro Trello](https://trello.com/b/EQFx2d39/controle-de-gasto-pessoal-cgp).
