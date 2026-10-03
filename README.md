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

`/health` confirma que a API responde.

## Usuários (S1-02)

A migração inicial cria `users` com `id` único, `email` único e `password_hash` (hash Argon2). Ela é aplicada automaticamente ao iniciar o backend.

O acesso ao banco usa `SessionLocal` em `backend/app/database.py`. O `UserRepository`, em `backend/app/repositories.py`, cria usuários recebendo e-mail e senha, gera o hash antes de salvar e permite buscar por ID ou e-mail.

Para aplicar a migração manualmente:

```sh
docker compose exec backend alembic upgrade head
```

## Sprint 1

As tarefas estão em [KANBAN_SPRINT_1.md](KANBAN_SPRINT_1.md) e no [quadro Trello](https://trello.com/b/EQFx2d39/controle-de-gasto-pessoal-cgp).
