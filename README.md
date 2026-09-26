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

Nesta etapa, `/health` confirma apenas que a API responde. A conexão com o banco e as migrations serão implementadas na S1-02.

## Sprint 1

As tarefas estão em [KANBAN_SPRINT_1.md](KANBAN_SPRINT_1.md) e no [quadro Trello](https://trello.com/b/EQFx2d39/controle-de-gasto-pessoal-cgp).
