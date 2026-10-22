import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import psycopg
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import connect
from app.schemas import UsuarioSaida

# Sem configuração, os tokens deixam de valer ao reiniciar a API.
JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_hex(32)
bearer = HTTPBearer(auto_error=False)


def criar_token(usuario_id: int) -> str:
    sessao_id = secrets.token_hex(16)
    expira_em = datetime.now(timezone.utc) + timedelta(minutes=30)
    with connect() as connection:
        connection.execute("DELETE FROM public.sessoes WHERE expira_em <= now()")
        connection.execute(
            "INSERT INTO public.sessoes (id, usuario_id, expira_em) VALUES (%s, %s, %s)",
            (sessao_id, usuario_id, expira_em),
        )
    return jwt.encode(
        {"sub": str(usuario_id), "jti": sessao_id, "exp": expira_em},
        JWT_SECRET,
        algorithm="HS256",
    )


def encerrar_sessao(token: str) -> None:
    # A rota de logout já validou o token pela dependência usuario_autenticado.
    dados = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"verify_exp": False})
    with connect() as connection:
        connection.execute("DELETE FROM public.sessoes WHERE id = %s", (dados["jti"],))


def usuario_autenticado(
    credenciais: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> UsuarioSaida:
    erro = HTTPException(
        status_code=401,
        detail="Autenticação ausente ou token inválido.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credenciais is None:
        raise erro
    try:
        dados = jwt.decode(
            credenciais.credentials,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["sub", "jti", "exp"]},
        )
        usuario_id = int(dados["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError) as error:
        raise erro from error

    try:
        with connect() as connection:
            linha = connection.execute(
                "SELECT u.id_dadopessoal, u.nome, u.email FROM public.dados_pessoal u "
                "JOIN public.sessoes s ON s.usuario_id = u.id_dadopessoal "
                "WHERE u.id_dadopessoal = %s AND s.id = %s AND s.expira_em > now()",
                (usuario_id, dados["jti"]),
            ).fetchone()
    except psycopg.OperationalError as error:
        raise HTTPException(status_code=503, detail="Banco indisponível") from error

    if linha is None:
        raise erro
    return UsuarioSaida(id=linha[0], nome=linha[1], email=linha[2])
