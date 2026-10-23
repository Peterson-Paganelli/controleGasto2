"""Gastos do usuário autenticado (S1-06).

Recurso usado nesta sprint para provar o isolamento de dados por usuário:
- o dono do registro vem sempre do token (usuario_autenticado), nunca do corpo
  nem da URL;
- toda consulta SQL filtra por id_dadospessoal = dono, então registros de outro
  usuário não são listados, vistos, alterados nem excluídos;
- registro de outro usuário e registro inexistente respondem igual (404), sem
  revelar que o registro existe;
- o router inteiro exige autenticação (401 sem token válido).
"""

from contextlib import contextmanager

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Path

from app.auth import usuario_autenticado
from app.database import connect
from app.schemas import GastoEntrada, GastoSaida, UsuarioSaida

# A dependência no router garante a autenticação mesmo em rotas futuras.
router = APIRouter(
    prefix="/gastos", tags=["gastos"], dependencies=[Depends(usuario_autenticado)]
)

COLUNAS = "id_gastos, valor, data_tabela, descricao"
ID_GASTO = Path(ge=1, le=2_147_483_647)


@contextmanager
def _banco():
    try:
        with connect() as conexao:
            yield conexao
    except psycopg.OperationalError as error:
        raise HTTPException(status_code=503, detail="Banco indisponível") from error


def _saida(linha: tuple) -> GastoSaida:
    return GastoSaida(id=linha[0], valor=linha[1], data=linha[2], descricao=linha[3])


def _nao_encontrado() -> HTTPException:
    return HTTPException(status_code=404, detail="Gasto não encontrado.")


@router.get("", response_model=list[GastoSaida])
def listar(usuario: UsuarioSaida = Depends(usuario_autenticado)) -> list[GastoSaida]:
    with _banco() as conexao:
        linhas = conexao.execute(
            f"SELECT {COLUNAS} FROM public.tabela_gastos WHERE id_dadospessoal = %s "
            "ORDER BY data_tabela DESC, id_gastos DESC",
            (usuario.id,),
        ).fetchall()
    return [_saida(linha) for linha in linhas]


@router.post("", status_code=201, response_model=GastoSaida)
def criar(
    dados: GastoEntrada, usuario: UsuarioSaida = Depends(usuario_autenticado)
) -> GastoSaida:
    with _banco() as conexao:
        linha = conexao.execute(
            "INSERT INTO public.tabela_gastos (id_dadospessoal, valor, data_tabela, descricao) "
            f"VALUES (%s, %s, %s, %s) RETURNING {COLUNAS}",
            (usuario.id, dados.valor, dados.data, dados.descricao),
        ).fetchone()
    return _saida(linha)


@router.get("/{id_gasto}", response_model=GastoSaida)
def visualizar(
    id_gasto: int = ID_GASTO, usuario: UsuarioSaida = Depends(usuario_autenticado)
) -> GastoSaida:
    with _banco() as conexao:
        linha = conexao.execute(
            f"SELECT {COLUNAS} FROM public.tabela_gastos "
            "WHERE id_gastos = %s AND id_dadospessoal = %s",
            (id_gasto, usuario.id),
        ).fetchone()
    if linha is None:
        raise _nao_encontrado()
    return _saida(linha)


@router.put("/{id_gasto}", response_model=GastoSaida)
def alterar(
    dados: GastoEntrada,
    id_gasto: int = ID_GASTO,
    usuario: UsuarioSaida = Depends(usuario_autenticado),
) -> GastoSaida:
    with _banco() as conexao:
        linha = conexao.execute(
            "UPDATE public.tabela_gastos SET valor = %s, data_tabela = %s, descricao = %s "
            f"WHERE id_gastos = %s AND id_dadospessoal = %s RETURNING {COLUNAS}",
            (dados.valor, dados.data, dados.descricao, id_gasto, usuario.id),
        ).fetchone()
    if linha is None:
        raise _nao_encontrado()
    return _saida(linha)


@router.delete("/{id_gasto}", status_code=204)
def excluir(
    id_gasto: int = ID_GASTO, usuario: UsuarioSaida = Depends(usuario_autenticado)
) -> None:
    with _banco() as conexao:
        linha = conexao.execute(
            "DELETE FROM public.tabela_gastos "
            "WHERE id_gastos = %s AND id_dadospessoal = %s RETURNING id_gastos",
            (id_gasto, usuario.id),
        ).fetchone()
    if linha is None:
        raise _nao_encontrado()
