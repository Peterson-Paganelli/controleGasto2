import { useState, type FormEvent } from 'react'
import { api, type Token, type Usuario } from './api'

export default function App() {
  const [modo, setModo] = useState<'login' | 'cadastro'>('login')
  const [email, setEmail] = useState('')
  const [erro, setErro] = useState('')
  const [mensagem, setMensagem] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [sessao, setSessao] = useState<{ token: string; usuario: Usuario } | null>(null)
  const cadastro = modo === 'cadastro'

  function trocarModo(novoModo: 'login' | 'cadastro') {
    setModo(novoModo)
    setErro('')
    setMensagem('')
  }

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (enviando) return
    const formulario = evento.currentTarget
    const campos = new FormData(formulario)
    const senha = String(campos.get('senha') || '')
    const emailNormalizado = email.trim().toLowerCase()
    setErro('')
    setMensagem('')
    setEnviando(true)

    try {
      if (new TextEncoder().encode(senha).length > 72) {
        throw new Error('A senha deve ter no máximo 72 bytes. Acentos podem ocupar mais de um byte.')
      }
      if (cadastro) {
        const nome = String(campos.get('nome') || '').trim()
        const cpf = String(campos.get('cpf') || '').replace(/[.\-\s]/g, '')
        const telefone = String(campos.get('telefone') || '').replace(/\D/g, '')
        if (!nome) throw new Error('Informe o nome.')
        if (!/^[0-9]{11}$/.test(cpf)) throw new Error('O CPF deve ter 11 dígitos.')
        if (!/^[0-9]{10,13}$/.test(telefone)) throw new Error('Informe um telefone válido com DDD.')
        const usuario = await api<Usuario>('/cadastro', {
          method: 'POST',
          body: JSON.stringify({ nome, cpf, telefone, email: emailNormalizado, senha }),
        })
        formulario.reset()
        setEmail(usuario.email)
        setModo('login')
        setMensagem('Cadastro realizado! Entre com seu e-mail e senha.')
      } else {
        const token = await api<Token>('/login', {
          method: 'POST',
          body: JSON.stringify({ email: emailNormalizado, senha }),
        })
        const usuario = await api<Usuario>('/me', {
          headers: { Authorization: `Bearer ${token.access_token}` },
        })
        formulario.reset()
        setSessao({ token: token.access_token, usuario })
      }
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível concluir. Tente novamente.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main>
      <header className="marca">
        <span className="simbolo" aria-hidden="true">CGP</span>
        <span>Controle de Gasto Pessoal</span>
      </header>

      <section className="cartao" aria-labelledby="titulo">
        {sessao ? (
          <>
            <p className="etiqueta">CONTA CONECTADA</p>
            <h1 id="titulo">Olá, {sessao.usuario.nome}!</h1>
            <p className="descricao">Você entrou na sua conta.</p>
            <p className="email-usuario">{sessao.usuario.email}</p>
            <button type="button" className="principal" onClick={() => {
              setSessao(null)
              setEmail('')
              setMensagem('Você saiu da conta.')
            }}>Sair da conta</button>
          </>
        ) : (
          <>
            <nav className="modos" aria-label="Acesso à conta">
              <button type="button" aria-pressed={!cadastro} disabled={enviando}
                onClick={() => trocarModo('login')}>Entrar</button>
              <button type="button" aria-pressed={cadastro} disabled={enviando}
                onClick={() => trocarModo('cadastro')}>Criar conta</button>
            </nav>
            <h1 id="titulo">{cadastro ? 'Crie sua conta' : 'Bem-vindo de volta'}</h1>
            <p className="descricao">{cadastro
              ? 'Comece a organizar seus gastos em um só lugar.'
              : 'Entre para acessar sua conta.'}</p>

            {mensagem && <p className="sucesso" role="status">{mensagem}</p>}
            {erro && <p className="erro" role="alert" id="erro-formulario">{erro}</p>}

            <form key={modo} onSubmit={enviar} aria-describedby={erro ? 'erro-formulario' : undefined}>
              <fieldset disabled={enviando}>
                {cadastro && (
                  <>
                    <label htmlFor="nome">Nome completo</label>
                    <input id="nome" name="nome" autoComplete="name" required />
                    <label htmlFor="cpf">CPF</label>
                    <input id="cpf" name="cpf" inputMode="numeric" placeholder="000.000.000-00" required />
                    <label htmlFor="telefone">Telefone com DDD</label>
                    <input id="telefone" name="telefone" type="tel" autoComplete="tel"
                      placeholder="(47) 90000-0000" required />
                  </>
                )}
                <label htmlFor="email">E-mail</label>
                <input id="email" name="email" type="email" autoComplete="username" maxLength={254}
                  value={email} onChange={(evento) => setEmail(evento.target.value)} required />
                <label htmlFor="senha">Senha</label>
                <input id="senha" name="senha" type="password"
                  autoComplete={cadastro ? 'new-password' : 'current-password'}
                  minLength={cadastro ? 8 : undefined} required aria-describedby={cadastro ? 'dica-senha' : undefined} />
                {cadastro && <small id="dica-senha">Use pelo menos 8 caracteres e no máximo 72 bytes.</small>}
                <button className="principal" type="submit">{enviando ? 'Aguarde…' : cadastro ? 'Criar conta' : 'Entrar na conta'}</button>
              </fieldset>
            </form>
          </>
        )}
      </section>
      <p className="rodape">Um passo de cada vez para cuidar do seu dinheiro.</p>
    </main>
  )
}
