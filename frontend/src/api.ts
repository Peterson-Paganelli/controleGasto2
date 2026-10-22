export type Usuario = { id: number; nome: string; email: string }
export type Token = { access_token: string; token_type: string }

export async function api<T>(rota: string, opcoes: RequestInit = {}): Promise<T> {
  let resposta: Response
  try {
    resposta = await fetch(`/api${rota}`, {
      ...opcoes,
      headers: { 'Content-Type': 'application/json', ...opcoes.headers },
    })
  } catch {
    throw new Error('Não foi possível conectar ao serviço. Tente novamente.')
  }

  const corpo = await resposta.json().catch(() => null)
  if (resposta.status === 401) {
    throw new Error(rota === '/login' ? 'E-mail ou senha inválidos.' : 'Sua sessão expirou. Entre novamente.')
  }
  if (resposta.status === 409 || resposta.status === 422) {
    // A API retorna apenas campo e mensagem, sem os dados enviados.
    const mensagens = Array.isArray(corpo?.detail)
      ? corpo.detail.map((erro: { mensagem?: unknown } | null) => erro?.mensagem)
        .filter((mensagem: unknown) => typeof mensagem === 'string')
      : []
    throw new Error(mensagens.join(' ') || 'Confira os dados informados.')
  }
  if (!resposta.ok || corpo === null) {
    throw new Error('Serviço indisponível. Tente novamente em instantes.')
  }
  return corpo as T
}
