import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, ErroApi, type Usuario } from './api'

type Props = { token: string; aoEncerrar: (mensagem: string) => void }

export default function AreaInterna({ token, aoEncerrar }: Props) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [erro, setErro] = useState('')
  const [saindo, setSaindo] = useState(false)
  const [tentativa, setTentativa] = useState(0)

  useEffect(() => {
    let ativo = true
    setUsuario(null)
    setErro('')
    api<Usuario>('/me', { headers: { Authorization: `Bearer ${token}` } })
      .then((dados) => { if (ativo) setUsuario(dados) })
      .catch((falha) => {
        if (!ativo) return
        if (falha instanceof ErroApi && falha.status === 401) {
          aoEncerrar('Sua sessão expirou. Entre novamente.')
        } else {
          setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar sua conta.')
        }
      })
    return () => { ativo = false }
  }, [token, aoEncerrar, tentativa])

  async function sair() {
    setSaindo(true)
    setErro('')
    try {
      await api<void>('/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
      aoEncerrar('Você saiu da conta.')
    } catch (falha) {
      if (falha instanceof ErroApi && falha.status === 401) {
        aoEncerrar('Sua sessão expirou. Entre novamente.')
      } else {
        setErro(falha instanceof Error ? falha.message : 'Não foi possível sair. Tente novamente.')
      }
    } finally {
      setSaindo(false)
    }
  }

  return (
    <main className="area-interna">
      <header className="barra-interna">
        <div className="marca">
          <span className="simbolo" aria-hidden="true">CGP</span>
          <span>Controle de Gasto Pessoal</span>
        </div>
        <button className="botao-sair" type="button" onClick={sair} disabled={saindo}>
          {saindo ? 'Saindo…' : 'Sair da conta'}
        </button>
      </header>
      <nav className="menu-interno" aria-label="Área interna">
        <Link to="/app" aria-current="page">Visão geral</Link>
      </nav>
      {erro && <p className="erro" role="alert">{erro}</p>}
      {!usuario ? (
        erro ? <button type="button" className="principal" onClick={() => setTentativa(tentativa + 1)}>Tentar novamente</button>
          : <p role="status">Verificando sua sessão…</p>
      ) : (
        <>
          <section className="boas-vindas" aria-labelledby="titulo">
            <p className="etiqueta">ÁREA INTERNA</p>
            <h1 id="titulo">Olá, {usuario.nome}!</h1>
            <p className="descricao">Seu espaço para cuidar do dinheiro e organizar o dia a dia.</p>
          </section>
          <section className="cartao" aria-labelledby="minha-conta">
            <h2 id="minha-conta">Minha conta</h2>
            <p className="descricao">Você está conectado com o e-mail:</p>
            <p className="email-usuario">{usuario.email}</p>
          </section>
        </>
      )}
    </main>
  )
}
