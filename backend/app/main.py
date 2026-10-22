from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import connect, migrate
from app.schemas import CadastroEntrada, UsuarioSaida

# Constraints UNIQUE criadas na migration 001 -> campo exibido ao usuário.
CAMPOS_UNICOS = {
    "dados_pessoal_email_key": ("email", "E-mail já cadastrado."),
    "dados_pessoal_cpf_key": ("cpf", "CPF já cadastrado."),
    "dados_pessoal_numero_telefone_key": ("telefone", "Telefone já cadastrado."),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate()
    yield


app = FastAPI(title="CGP API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def erro_validacao(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Padroniza os erros de validação: {"detail": [{"campo", "mensagem"}]}."""
    erros = []
    for erro in exc.errors():
        if erro["type"] == "missing":
            mensagem = "Campo obrigatório."
        elif erro["type"] == "string_type":
            mensagem = "Valor inválido: envie um texto."
        else:
            mensagem = str(erro["msg"]).removeprefix("Value error, ")
        erros.append(
            {"campo": ".".join(str(parte) for parte in erro["loc"][1:]), "mensagem": mensagem}
        )
    return JSONResponse(status_code=422, content={"detail": erros})


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with connect() as connection:
            connection.execute("SELECT 1")
    except psycopg.Error as error:
        raise HTTPException(status_code=503, detail="Banco indisponível") from error
    return {"status": "ok"}


@app.post("/cadastro", status_code=201, response_model=UsuarioSaida)
def cadastrar(dados: CadastroEntrada) -> UsuarioSaida:
    # O hash bcrypt (custo 12) é gerado pela procedure p_criacaodeconta no banco.
    try:
        with connect() as connection:
            connection.execute(
                "CALL public.p_criacaodeconta(%s, %s, %s, %s, %s)",
                (dados.nome, dados.cpf, dados.telefone, dados.email, dados.senha),
            )
            linha = connection.execute(
                "SELECT id_dadopessoal, nome, email FROM public.dados_pessoal WHERE email = %s",
                (dados.email,),
            ).fetchone()
    except psycopg.errors.UniqueViolation as error:
        campo, mensagem = CAMPOS_UNICOS.get(
            error.diag.constraint_name, ("cadastro", "Dados já cadastrados.")
        )
        raise HTTPException(
            status_code=409, detail=[{"campo": campo, "mensagem": mensagem}]
        ) from error
    except psycopg.OperationalError as error:
        raise HTTPException(status_code=503, detail="Banco indisponível") from error

    return UsuarioSaida(id=linha[0], nome=linha[1], email=linha[2])
