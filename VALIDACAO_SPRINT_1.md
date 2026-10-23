# Item 11 — Como testar a Sprint 1

Os testes conferem cadastro, login, senhas BCrypt, isolamento dos gastos e as telas
em celular (360 px) e desktop (1440 px).

## O que cada arquivo faz

- `compose.testes.yaml`: inicia frontend, backend e um banco separado para testes.
- `backend/tests/`: confere cadastro, login, BCrypt e acesso aos gastos de cada usuário.
- `frontend/tests/api.test.mjs`: confere as mensagens e chamadas da interface.
- `frontend/e2e/sprint1.spec.mjs`: abre o navegador e faz cadastro, login e logout de verdade.
- `frontend/playwright.config.mjs`: define os tamanhos de tela usados pelo navegador.

## 1. Iniciar o projeto

Abra o Docker Desktop. No terminal, dentro da pasta do projeto, execute:

```sh
docker compose -f compose.testes.yaml up -d --build --wait
```

Abra <http://127.0.0.1:55173>. Espere a tela de login aparecer antes de continuar.
O banco desse ambiente serve apenas para testes; os dados normais do projeto não são alterados.

## 2. Testar o backend e o frontend

Execute um comando por vez, na pasta do projeto:

```sh
docker compose -f compose.testes.yaml exec backend python -m unittest discover -s tests -v
docker compose -f compose.testes.yaml exec frontend npm test
docker compose -f compose.testes.yaml exec frontend npm run build
```

O primeiro comando verifica também se as senhas usam BCrypt com custo mínimo 10
e se um usuário é impedido de acessar os gastos de outro. O último verifica se
a interface pode ser preparada para publicação.

## 3. Testar as telas no navegador

Instale Node.js 22.22 ou superior. Depois execute:

```sh
cd frontend
npm ci
npx playwright install chromium
npm run test:e2e
```

O teste repete os mesmos passos em 360 px e 1440 px. Ele confere se os campos e
botões são acessíveis e se não há rolagem horizontal. As imagens de login,
cadastro e área interna ficam na pasta `frontend/test-results/`.

Para ver o navegador executando os passos, use `npm run test:e2e -- --headed`.
Para usar o Edge já instalado, defina `$env:E2E_BROWSER_CHANNEL = 'msedge'` no
PowerShell; nesse caso, não precisa executar `npx playwright install chromium`.

## 4. Encerrar e limpar os testes

Volte à pasta do projeto com `cd ..` e execute:

```sh
docker compose -f compose.testes.yaml down --volumes
```

Isso apaga somente as contas e os dados do ambiente de testes. Para repetir todos
os testes, comece novamente pelo passo 1, com o banco vazio.

## Resultado

Validação de 22/10/2026: 55 testes do backend, 8 testes do frontend e 2 testes de
navegador aprovados. Build aprovado. BCrypt com custo 12, isolamento confirmado e
telas utilizáveis em 360 px e 1440 px. Nenhum erro crítico observado nos fluxos testados.

Os testes de navegador cuidam da interface. As verificações de segurança ficam
nos testes do backend, para não manter a mesma lógica em dois lugares.
Os gastos ainda são um recurso da API, sem tela própria nesta sprint.
