import re

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, field_validator

SENHA_MIN_CARACTERES = 8
SENHA_MAX_BYTES = 72  # limite do bcrypt, o mesmo validado no banco


class CadastroEntrada(BaseModel):
    nome: str
    cpf: str
    telefone: str
    email: str
    senha: str

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Informe o nome.")
        return valor

    @field_validator("cpf")
    @classmethod
    def validar_cpf(cls, valor: str) -> str:
        digitos = re.sub(r"[.\-\s]", "", valor)
        if not re.fullmatch(r"[0-9]{11}", digitos):
            raise ValueError("O CPF deve ter 11 dígitos.")
        return digitos

    @field_validator("telefone")
    @classmethod
    def validar_telefone(cls, valor: str) -> str:
        digitos = re.sub(r"\D", "", valor)
        if not 10 <= len(digitos) <= 13:
            raise ValueError("Informe um telefone válido com DDD.")
        return digitos

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor: str) -> str:
        valor = valor.strip().lower()
        try:
            return validate_email(valor, check_deliverability=False).normalized
        except EmailNotValidError as error:
            raise ValueError("Informe um e-mail válido.") from error

    @field_validator("senha")
    @classmethod
    def validar_senha(cls, valor: str) -> str:
        if len(valor) < SENHA_MIN_CARACTERES:
            raise ValueError(
                f"A senha deve ter pelo menos {SENHA_MIN_CARACTERES} caracteres."
            )
        if len(valor.encode("utf-8")) > SENHA_MAX_BYTES:
            raise ValueError(f"A senha deve ter no máximo {SENHA_MAX_BYTES} bytes.")
        return valor


class UsuarioSaida(BaseModel):
    """Resposta do cadastro: nunca inclui a senha nem o hash."""

    id: int
    nome: str
    email: str
