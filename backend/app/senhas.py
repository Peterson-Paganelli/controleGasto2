"""Geração e verificação de hashes BCrypt (S1-04).

O hash é calculado pelo pgcrypto do PostgreSQL, o mesmo mecanismo usado pelas
procedures p_criacaodeconta e validador_senhaeemail. Assim existe uma única
implementação de BCrypt no projeto e os hashes gerados aqui são compatíveis com
os gravados em dados_pessoal.senha.
"""

import hmac
import re

from app.database import connect

CUSTO_BCRYPT = 12  # padrão usado nas procedures do banco
CUSTO_MINIMO = 10  # exigido pelo critério de aceite da S1-04
CUSTO_MAXIMO = 31  # limite do pgcrypto
SENHA_MAX_BYTES = 72  # limite do bcrypt

HASH_BCRYPT_RE = re.compile(r"^\$2[aby]\$([0-9]{2})\$[./A-Za-z0-9]{53}$")


def _senha_valida(senha: object) -> bool:
    return isinstance(senha, str) and 1 <= len(senha.encode("utf-8")) <= SENHA_MAX_BYTES


def gerar_hash(senha: str, custo: int = CUSTO_BCRYPT) -> str:
    """Gera um hash BCrypt com salt aleatório. Recusa custo abaixo de 10."""
    if not _senha_valida(senha):
        raise ValueError(f"A senha deve conter entre 1 e {SENHA_MAX_BYTES} bytes.")
    if not CUSTO_MINIMO <= custo <= CUSTO_MAXIMO:
        raise ValueError(f"O custo do BCrypt deve estar entre {CUSTO_MINIMO} e {CUSTO_MAXIMO}.")
    with connect() as connection:
        return connection.execute(
            "SELECT public.crypt(%s, public.gen_salt('bf', %s::integer))", (senha, custo)
        ).fetchone()[0]


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Retorna True só se a senha corresponder ao hash. Entradas inválidas retornam False."""
    if not _senha_valida(senha):
        return False
    if not isinstance(hash_armazenado, str) or not HASH_BCRYPT_RE.fullmatch(hash_armazenado):
        return False
    with connect() as connection:
        recalculado = connection.execute(
            "SELECT public.crypt(%s, %s)", (senha, hash_armazenado)
        ).fetchone()[0]
    return hmac.compare_digest(recalculado, hash_armazenado)


def custo_do_hash(hash_armazenado: str) -> int:
    """Extrai o fator de custo de um hash BCrypt (ex.: $2a$12$... -> 12)."""
    correspondencia = HASH_BCRYPT_RE.fullmatch(hash_armazenado)
    if correspondencia is None:
        raise ValueError("Hash BCrypt inválido.")
    return int(correspondencia.group(1))
