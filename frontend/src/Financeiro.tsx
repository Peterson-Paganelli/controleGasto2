import { useEffect, useState, type FormEvent } from 'react'
import { api, ErroApi } from './api'

type Conta = { id: number; banco: string; agencia: string; numero: string }
type Cartao = { id: number; nome: string; dia_fechamento: number; conta_id: number | null }
type Lancamento = {
  id: number; descricao: string; valor: string; data: string
  categoria?: string; vencimento?: string | null; conta_id: number | null; cartao_id: number | null
}
type Aba = 'entradas' | 'gastos' | 'contas' | 'cartoes'
type Props = { token: string; aoEncerrar: (mensagem: string) => void }
const titulos: Record<Aba, string> = {
  entradas: 'Entradas', gastos: 'Gastos', contas: 'Contas bancárias', cartoes: 'Cartões',
}
const dinheiro = (valor: string) => Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const dataFormatada = (valor: string) => valor.split('-').reverse().join('/')

export default function Financeiro({ token, aoEncerrar }: Props) {
  const [aba, setAba] = useState<Aba>('entradas')
  const [contas, setContas] = useState<Conta[]>([])
  const [cartoes, setCartoes] = useState<Cartao[]>([])
  const [entradas, setEntradas] = useState<Lancamento[]>([])
  const [gastos, setGastos] = useState<Lancamento[]>([])
  const [edicao, setEdicao] = useState<Lancamento | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')
  const [atualizacao, setAtualizacao] = useState(0)
  const headers = { Authorization: `Bearer ${token}` }

  function mostrarErro(falha: unknown) {
    if (falha instanceof ErroApi && falha.status === 401) {
      aoEncerrar('Sua sessão expirou. Entre novamente.')
    } else {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível concluir a operação.')
    }
  }

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    setErro('')
    Promise.all([
      api<Conta[]>('/contas', { headers }), api<Cartao[]>('/cartoes', { headers }),
      api<Lancamento[]>('/entradas', { headers }), api<Lancamento[]>('/gastos', { headers }),
    ]).then(([contas, cartoes, entradas, gastos]) => {
      if (!ativo) return
      setContas(contas); setCartoes(cartoes); setEntradas(entradas); setGastos(gastos)
    }).catch(falha => { if (ativo) mostrarErro(falha) })
      .finally(() => { if (ativo) setCarregando(false) })
    return () => { ativo = false }
  }, [token, atualizacao, aoEncerrar])

  function trocarAba(nova: Aba) {
    setAba(nova); setEdicao(null); setErro(''); setSucesso('')
  }

  async function salvar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const formulario = evento.currentTarget
    const campos = new FormData(formulario)
    const texto = (campo: string) => String(campos.get(campo) ?? '').trim()
    const vinculos = { conta_id: Number(texto('conta_id')) || null, cartao_id: Number(texto('cartao_id')) || null }
    let corpo: object
    if (aba === 'contas') {
      corpo = { banco: texto('banco'), agencia: texto('agencia'), numero: texto('numero') }
    } else if (aba === 'cartoes') {
      corpo = { nome: texto('nome'), dia_fechamento: Number(texto('dia_fechamento')), conta_id: vinculos.conta_id }
    } else {
      corpo = { descricao: texto('descricao'), valor: texto('valor'), data: texto('data'), ...vinculos,
        ...(aba === 'gastos' ? { categoria: texto('categoria'), vencimento: texto('vencimento') || null } : {}) }
    }
    setSalvando(true); setErro(''); setSucesso('')
    try {
      await api(`/${aba}${edicao ? `/${edicao.id}` : ''}`, {
        method: edicao ? 'PUT' : 'POST', headers, body: JSON.stringify(corpo),
      })
      formulario.reset(); setEdicao(null); setSucesso('Registro salvo.'); setAtualizacao(valor => valor + 1)
    } catch (falha) { mostrarErro(falha) }
    finally { setSalvando(false) }
  }

  async function excluir(gasto: Lancamento) {
    if (!window.confirm(`Excluir o gasto “${gasto.descricao}”?`)) return
    setSalvando(true); setErro(''); setSucesso('')
    try {
      await api(`/gastos/${gasto.id}`, { method: 'DELETE', headers })
      setEdicao(null); setSucesso('Gasto excluído.'); setAtualizacao(valor => valor + 1)
    } catch (falha) { mostrarErro(falha) }
    finally { setSalvando(false) }
  }

  const nomeConta = (id: number | null) => {
    const conta = contas.find(conta => conta.id === id)
    return conta ? `${conta.banco} · ${conta.agencia} / ${conta.numero}` : 'Sem conta'
  }
  const nomeCartao = (id: number | null) => cartoes.find(cartao => cartao.id === id)?.nome || 'Sem cartão'

  return <section className="financeiro" aria-label="Cadastros financeiros">
    <nav className="abas-financeiras" aria-label="Cadastros">
      {(Object.keys(titulos) as Aba[]).map(item => <button key={item} type="button"
        aria-pressed={aba === item} disabled={salvando} onClick={() => trocarAba(item)}>{titulos[item]}</button>)}
    </nav>
    <h2>{titulos[aba]}</h2>
    {erro && <p className="erro" role="alert">{erro}</p>}
    {sucesso && <p className="sucesso" role="status">{sucesso}</p>}
    {carregando ? <p role="status">Carregando cadastros…</p> : <>
      {erro && <button type="button" onClick={() => setAtualizacao(valor => valor + 1)}>Atualizar cadastros</button>}
      <form className="cartao" key={`${aba}-${edicao?.id ?? 'novo'}`} onSubmit={salvar}>
        <h3>{edicao ? 'Editar gasto' : 'Novo cadastro'}</h3>
        <fieldset disabled={salvando}>
          {aba === 'contas' ? <>
            <label htmlFor="banco">Banco</label><input id="banco" name="banco" required maxLength={100} />
            <label htmlFor="agencia">Agência</label><input id="agencia" name="agencia" required maxLength={30} />
            <label htmlFor="numero">Número da conta</label><input id="numero" name="numero" required maxLength={30} />
          </> : aba === 'cartoes' ? <>
            <label htmlFor="nome-cartao">Nome do cartão</label><input id="nome-cartao" name="nome" required maxLength={100} />
            <label htmlFor="fechamento">Dia de fechamento</label><input id="fechamento" name="dia_fechamento" type="number" min="1" max="31" step="1" required />
            <small>Dia informativo para organizar os registros.</small>
          </> : <>
            <label htmlFor="descricao">Descrição</label><input id="descricao" name="descricao" required maxLength={200} defaultValue={edicao?.descricao} />
            <label htmlFor="valor">Valor (R$)</label><input id="valor" name="valor" type="number" min="0.01" max="999999999999.99" step="0.01" required defaultValue={edicao?.valor} />
            <label htmlFor="data">Data do lançamento</label><input id="data" name="data" type="date" required defaultValue={edicao?.data} />
            {aba === 'gastos' && <>
              <label htmlFor="categoria">Categoria</label><input id="categoria" name="categoria" required maxLength={100} defaultValue={edicao?.categoria} placeholder="Ex.: Alimentação" />
              <label htmlFor="vencimento">Vencimento (opcional)</label><input id="vencimento" name="vencimento" type="date" defaultValue={edicao?.vencimento ?? ''} />
            </>}
          </>}
          {aba !== 'contas' && <>
            <label htmlFor="conta">Conta bancária (opcional)</label>
            <select id="conta" name="conta_id" defaultValue={edicao?.conta_id ?? ''}>
              <option value="">Sem conta</option>{contas.map(conta => <option key={conta.id} value={conta.id}>{nomeConta(conta.id)}</option>)}
            </select>
          </>}
          {(aba === 'entradas' || aba === 'gastos') && <>
            <label htmlFor="cartao">Cartão (opcional)</label>
            <select id="cartao" name="cartao_id" defaultValue={edicao?.cartao_id ?? ''}>
              <option value="">Sem cartão</option>{cartoes.map(cartao => <option key={cartao.id} value={cartao.id}>{cartao.nome}</option>)}
            </select>
          </>}
          <button className="principal" type="submit">{salvando ? 'Salvando…' : edicao ? 'Salvar alterações' : 'Salvar cadastro'}</button>
          {edicao && <button type="button" className="botao-sair" onClick={() => setEdicao(null)}>Cancelar edição</button>}
        </fieldset>
      </form>
      <ul className="lista-financeira">
        {aba === 'contas' ? contas.map(conta => <li key={conta.id}><strong>{conta.banco}</strong><p>Agência {conta.agencia} · Conta {conta.numero}</p></li>)
          : aba === 'cartoes' ? cartoes.map(cartao => <li key={cartao.id}><strong>{cartao.nome}</strong><p>Fechamento: dia {cartao.dia_fechamento}</p><p>{nomeConta(cartao.conta_id)}</p></li>)
            : (aba === 'entradas' ? entradas : gastos).map(item => <li key={item.id}>
              <strong>{item.descricao} · {dinheiro(item.valor)}</strong><p>Data: {dataFormatada(item.data)}</p>
              {aba === 'gastos' && <p>{item.categoria} · {item.vencimento ? `Vence em ${dataFormatada(item.vencimento)}` : 'Sem vencimento'}</p>}
              <p>{nomeConta(item.conta_id)} · {nomeCartao(item.cartao_id)}</p>
              {aba === 'gastos' && <div className="acoes-gasto">
                <button type="button" disabled={salvando} onClick={() => { setEdicao(item); setErro(''); setSucesso('') }}>Editar</button>
                <button type="button" disabled={salvando} onClick={() => excluir(item)}>Excluir</button>
              </div>}
            </li>)}
      </ul>
      {(aba === 'contas' ? contas : aba === 'cartoes' ? cartoes : aba === 'entradas' ? entradas : gastos).length === 0 && <p>Nenhum registro cadastrado.</p>}
    </>}
  </section>
}
