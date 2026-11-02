"""Cadastros simples da Sprint 2. Todos usam o usuário do token."""
import psycopg
from fastapi import APIRouter, Depends, HTTPException

from app.auth import usuario_autenticado
from app.gastos import _banco
from app.schemas import (
    CartaoEntrada, CartaoSaida, ContaEntrada, ContaSaida,
    EntradaFinanceira, EntradaFinanceiraSaida, UsuarioSaida,
)
from app.vinculos import validar_vinculos

router = APIRouter(tags=["financeiro"], dependencies=[Depends(usuario_autenticado)])


@router.get("/contas", response_model=list[ContaSaida])
def listar_contas(usuario: UsuarioSaida = Depends(usuario_autenticado)):
    with _banco() as conexao:
        linhas = conexao.execute(
            "SELECT id, banco, agencia, numero FROM public.contas WHERE usuario_id = %s ORDER BY id DESC",
            (usuario.id,),
        ).fetchall()
    return [ContaSaida(id=id, banco=banco, agencia=agencia, numero=numero)
            for id, banco, agencia, numero in linhas]


@router.post("/contas", status_code=201, response_model=ContaSaida)
def criar_conta(dados: ContaEntrada, usuario: UsuarioSaida = Depends(usuario_autenticado)):
    try:
        with _banco() as conexao:
            id = conexao.execute(
                "INSERT INTO public.contas (usuario_id, banco, agencia, numero) VALUES (%s, %s, %s, %s) RETURNING id",
                (usuario.id, dados.banco, dados.agencia, dados.numero),
            ).fetchone()[0]
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(status_code=409, detail=[{
            "campo": "numero", "mensagem": "Já existe uma conta com essa agência e número."
        }]) from error
    return ContaSaida(id=id, **dados.model_dump())


@router.get("/cartoes", response_model=list[CartaoSaida])
def listar_cartoes(usuario: UsuarioSaida = Depends(usuario_autenticado)):
    with _banco() as conexao:
        linhas = conexao.execute(
            "SELECT id, nome, dia_fechamento, conta_id FROM public.cartoes WHERE usuario_id = %s ORDER BY id DESC",
            (usuario.id,),
        ).fetchall()
    return [CartaoSaida(id=id, nome=nome, dia_fechamento=dia, conta_id=conta)
            for id, nome, dia, conta in linhas]


@router.post("/cartoes", status_code=201, response_model=CartaoSaida)
def criar_cartao(dados: CartaoEntrada, usuario: UsuarioSaida = Depends(usuario_autenticado)):
    with _banco() as conexao:
        validar_vinculos(conexao, usuario.id, dados.conta_id)
        id = conexao.execute(
            "INSERT INTO public.cartoes (usuario_id, nome, dia_fechamento, conta_id) VALUES (%s, %s, %s, %s) RETURNING id",
            (usuario.id, dados.nome, dados.dia_fechamento, dados.conta_id),
        ).fetchone()[0]
    return CartaoSaida(id=id, **dados.model_dump())


@router.get("/entradas", response_model=list[EntradaFinanceiraSaida])
def listar_entradas(usuario: UsuarioSaida = Depends(usuario_autenticado)):
    with _banco() as conexao:
        linhas = conexao.execute(
            "SELECT id, valor, data, descricao, conta_id, cartao_id FROM public.entradas "
            "WHERE usuario_id = %s ORDER BY data DESC, id DESC", (usuario.id,),
        ).fetchall()
    return [EntradaFinanceiraSaida(id=id, valor=valor, data=data, descricao=descricao,
                                  conta_id=conta, cartao_id=cartao)
            for id, valor, data, descricao, conta, cartao in linhas]


@router.post("/entradas", status_code=201, response_model=EntradaFinanceiraSaida)
def criar_entrada(dados: EntradaFinanceira, usuario: UsuarioSaida = Depends(usuario_autenticado)):
    with _banco() as conexao:
        validar_vinculos(conexao, usuario.id, dados.conta_id, dados.cartao_id)
        id = conexao.execute(
            "INSERT INTO public.entradas (usuario_id, valor, data, descricao, conta_id, cartao_id) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (usuario.id, dados.valor, dados.data, dados.descricao, dados.conta_id, dados.cartao_id),
        ).fetchone()[0]
    return EntradaFinanceiraSaida(id=id, **dados.model_dump())
