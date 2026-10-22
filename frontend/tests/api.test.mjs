import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { api, ErroApi } from '../src/api.ts'

const fetchOriginal = globalThis.fetch
afterEach(() => { globalThis.fetch = fetchOriginal })

test('envia JSON pelo proxy e usa o token nas rotas protegidas', async () => {
  globalThis.fetch = async (url, opcoes) => {
    assert.equal(url, '/api/me')
    assert.equal(opcoes.headers.Authorization, 'Bearer token-de-teste')
    return Response.json({ id: 1, nome: 'Teste', email: 'teste@example.com' })
  }
  const usuario = await api('/me', { headers: { Authorization: 'Bearer token-de-teste' } })
  assert.equal(usuario.id, 1)
})

test('cadastro envia os dados no corpo da requisição', async () => {
  const dados = { nome: 'Teste', email: 'teste@example.com', senha: 'senha-ficticia' }
  globalThis.fetch = async (url, opcoes) => {
    assert.equal(url, '/api/cadastro')
    assert.equal(opcoes.method, 'POST')
    assert.equal(opcoes.headers['Content-Type'], 'application/json')
    assert.deepEqual(JSON.parse(opcoes.body), dados)
    return Response.json({ id: 1, nome: dados.nome, email: dados.email }, { status: 201 })
  }
  assert.equal((await api('/cadastro', { method: 'POST', body: JSON.stringify(dados) })).id, 1)
})

test('credenciais inválidas exibem mensagem sem reproduzir detalhes internos', async () => {
  globalThis.fetch = async () => Response.json({ detail: 'senha-ficticia e token-interno' }, { status: 401 })
  await assert.rejects(api('/login'), { message: 'E-mail ou senha inválidos.' })
  await assert.rejects(api('/me'), { message: 'Sua sessão expirou. Entre novamente.' })
})

test('exibe somente mensagens de validação e duplicidade, sem os valores enviados', async () => {
  for (const status of [409, 422]) {
    globalThis.fetch = async () => Response.json({
      detail: [{ campo: 'email', mensagem: 'E-mail já cadastrado.', input: 'senha-ficticia' }],
    }, { status })
    await assert.rejects(api('/cadastro'), { message: 'E-mail já cadastrado.' })
  }
})

test('falhas do servidor e respostas inesperadas usam mensagem genérica', async () => {
  for (const resposta of [
    Response.json({ detail: 'senha-ficticia e hash-interno' }, { status: 500 }),
    new Response('erro interno com token', { status: 502 }),
  ]) {
    globalThis.fetch = async () => resposta
    await assert.rejects(api('/login'), { message: 'Serviço indisponível. Tente novamente em instantes.' })
  }
})

test('falha de conexão não expõe a mensagem técnica', async () => {
  globalThis.fetch = async () => { throw new Error('detalhe interno') }
  await assert.rejects(api('/login'), { message: 'Não foi possível conectar ao serviço. Tente novamente.' })
})

test('logout envia o token e aceita a resposta 204 sem corpo', async () => {
  globalThis.fetch = async (url, opcoes) => {
    assert.equal(url, '/api/logout')
    assert.equal(opcoes.method, 'POST')
    assert.equal(opcoes.headers.Authorization, 'Bearer token-de-teste')
    return new Response(null, { status: 204 })
  }
  assert.equal(await api('/logout', {
    method: 'POST', headers: { Authorization: 'Bearer token-de-teste' },
  }), undefined)
})

test('identifica o 401 para a interface encerrar a sessão local', async () => {
  globalThis.fetch = async () => Response.json({ detail: 'token inválido' }, { status: 401 })
  await assert.rejects(api('/me'), (erro) => erro instanceof ErroApi && erro.status === 401)
})
