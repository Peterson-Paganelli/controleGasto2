import re
from datetime import date
from decimal import Decimal

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, Field, field_serializer, field_validator

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


class LoginEntrada(BaseModel):
    email: str
    senha: str


class TokenSaida(BaseModel):
    access_token: str
    token_type: str = "bearer"


VALOR_LIMITE = Decimal(10) ** 12  # numeric(14, 2) comporta até 999.999.999.999,99
DESCRICAO_MAX_CARACTERES = 200


class GastoEntrada(BaseModel):
    """Dados de um gasto. O dono nunca vem do corpo: é sempre o usuário autenticado."""

    valor: Decimal
    data: date
    descricao: str
    categoria: str = Field(default="Outros", min_length=1, max_length=100)
    vencimento: date | None = None
    conta_id: int | None = Field(default=None, ge=1, le=2_147_483_647)
    cartao_id: int | None = Field(default=None, ge=1, le=2_147_483_647)

    @field_validator("categoria")
    @classmethod
    def validar_categoria(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Informe a categoria.")
        return valor

    @field_validator("valor")
    @classmethod
    def validar_valor(cls, valor: Decimal) -> Decimal:
        if not valor.is_finite():
            raise ValueError("Informe um valor numérico válido.")
        if valor <= 0:
            raise ValueError("O valor deve ser maior que zero.")
        if valor.as_tuple().exponent < -2:
            raise ValueError("O valor deve ter no máximo 2 casas decimais.")
        if valor >= VALOR_LIMITE:
            raise ValueError("O valor informado é grande demais.")
        return valor.quantize(Decimal("0.01"))

    @field_validator("descricao")
    @classmethod
    def validar_descricao(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Informe a descrição.")
        if len(valor) > DESCRICAO_MAX_CARACTERES:
            raise ValueError(
                f"A descrição deve ter no máximo {DESCRICAO_MAX_CARACTERES} caracteres."
            )
        return valor


class GastoSaida(BaseModel):
    id: int
    valor: Decimal
    data: date
    descricao: str
    categoria: str = "Outros"
    vencimento: date | None = None
    conta_id: int | None = None
    cartao_id: int | None = None

    @field_serializer("valor")
    def serializar_valor(self, valor: Decimal) -> str:
        return f"{valor:.2f}"  # texto com 2 casas, sem perda de precisão


class EntradaFinanceira(BaseModel):
    valor: Decimal
    data: date
    descricao: str
    conta_id: int | None = Field(default=None, ge=1, le=2_147_483_647)
    cartao_id: int | None = Field(default=None, ge=1, le=2_147_483_647)

    @field_validator("valor")
    @classmethod
    def validar_valor(cls, valor: Decimal) -> Decimal:
        return GastoEntrada.validar_valor(valor)

    @field_validator("descricao")
    @classmethod
    def validar_descricao(cls, valor: str) -> str:
        return GastoEntrada.validar_descricao(valor)


class EntradaFinanceiraSaida(EntradaFinanceira):
    id: int

    @field_serializer("valor")
    def serializar_valor(self, valor: Decimal) -> str:
        return f"{valor:.2f}"


class ContaEntrada(BaseModel):
    banco: str = Field(min_length=1, max_length=100)
    agencia: str = Field(min_length=1, max_length=30)
    numero: str = Field(min_length=1, max_length=30)

    @field_validator("banco", "agencia", "numero")
    @classmethod
    def validar_texto(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Preencha o campo.")
        return valor


class ContaSaida(ContaEntrada):
    id: int


class CartaoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    dia_fechamento: int = Field(strict=True, ge=1, le=31)
    conta_id: int | None = Field(default=None, ge=1, le=2_147_483_647)

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor: str) -> str:
        return ContaEntrada.validar_texto(valor)


class CartaoSaida(CartaoEntrada):
    id: int
