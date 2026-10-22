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
    return jwt.encode(
        {"sub": str(usuario_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
        JWT_SECRET,
        algorithm="HS256",
    )


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
            options={"require": ["sub", "exp"]},
        )
        usuario_id = int(dados["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError) as error:
        raise erro from error

    try:
        with connect() as connection:
            linha = connection.execute(
                "SELECT id_dadopessoal, nome, email FROM public.dados_pessoal "
                "WHERE id_dadopessoal = %s",
                (usuario_id,),
            ).fetchone()
    except psycopg.OperationalError as error:
        raise HTTPException(status_code=503, detail="Banco indisponível") from error

    if linha is None:
        raise erro
    return UsuarioSaida(id=linha[0], nome=linha[1], email=linha[2])
