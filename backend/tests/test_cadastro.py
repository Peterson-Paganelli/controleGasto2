import asyncio
import json
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.database import connect, migrate
from app.main import app, cadastrar, erro_validacao
from app.schemas import CadastroEntrada
from app.senhas import gerar_hash

VALIDO = {
    "nome": "  Maria Teste  ",
    "cpf": "987.654.321-00",
    "telefone": "(47) 90000-0001",
    "email": "  MARIA@Cadastro.Example.com ",
    "senha": "senha-de-teste",
}


def dados(**alteracoes) -> CadastroEntrada:
    return CadastroEntrada(**{**VALIDO, **alteracoes})


class CadastroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("POSTGRES_DB", "").endswith("_test"):
            raise RuntimeError("Execute os testes em um banco com sufixo _test.")
        migrate()

    def setUp(self):
        self.addCleanup(self.limpar)

    def limpar(self):
        # cadastrar() confirma a transação, então os registros precisam ser removidos.
        with connect() as connection:
            connection.execute(
                "DELETE FROM public.dados_pessoal WHERE email LIKE '%@cadastro.example.com'"
            )

    def test_cadastro_valido_cria_usuario_com_hash_bcrypt(self):
        with patch("app.main.gerar_hash", wraps=gerar_hash) as gerar:
            saida = cadastrar(dados())
        gerar.assert_called_once_with("senha-de-teste")
        self.assertEqual(saida.nome, "Maria Teste")
        self.assertEqual(saida.email, "maria@cadastro.example.com")
        with connect() as connection:
            cpf, telefone, senha = connection.execute(
                "SELECT cpf, numero_telefone, senha FROM public.dados_pessoal WHERE id_dadopessoal = %s",
                (saida.id,),
            ).fetchone()
            login = connection.execute(
                "SELECT public.validador_senhaeemail(%s, %s)",
                ("maria@cadastro.example.com", "senha-de-teste"),
            ).fetchone()[0]
        self.assertEqual(cpf, "98765432100")
        self.assertEqual(telefone, "47900000001")
        self.assertRegex(senha, r"^\$2[aby]\$(1[0-9]|[2-3][0-9])\$")  # custo >= 10
        self.assertNotEqual(senha, "senha-de-teste")
        self.assertTrue(login)

    def test_resposta_nao_expoe_senha_nem_hash(self):
        corpo = cadastrar(dados()).model_dump()
        self.assertEqual(set(corpo), {"id", "nome", "email"})

    def test_usuario_cadastrado_consegue_fazer_login_e_acessar_me(self):
        usuario = cadastrar(dados())
        client = TestClient(app)
        resposta = client.post("/login", json={"email": usuario.email, "senha": VALIDO["senha"]})
        self.assertEqual(resposta.status_code, 200)
        token = resposta.json()["access_token"]
        resposta = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), usuario.model_dump())
        resposta = client.post("/login", json={"email": usuario.email, "senha": "errada"})
        self.assertEqual(resposta.status_code, 401)
        segunda_sessao = client.post("/login", json={"email": usuario.email, "senha": VALIDO["senha"]})
        outro_token = segunda_sessao.json()["access_token"]
        self.assertNotEqual(token, outro_token)
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(client.post("/logout", headers=headers).status_code, 204)
        self.assertEqual(client.get("/me", headers=headers).status_code, 401)
        resposta = client.get("/me", headers={"Authorization": f"Bearer {outro_token}"})
        self.assertEqual(resposta.status_code, 200)

    def test_duplicidade_retorna_409_indicando_o_campo(self):
        cadastrar(dados())
        for alteracoes, campo in (
            ({"cpf": "98765432101", "telefone": "47900000002"}, "email"),
            ({"email": "outro@cadastro.example.com", "telefone": "47900000002"}, "cpf"),
            ({"email": "outro@cadastro.example.com", "cpf": "98765432101"}, "telefone"),
        ):
            with self.assertRaises(HTTPException) as falha:
                cadastrar(dados(**alteracoes))
            self.assertEqual(falha.exception.status_code, 409)
            self.assertEqual(falha.exception.detail[0]["campo"], campo)

    def test_email_repetido_ignora_maiusculas(self):
        cadastrar(dados())
        with self.assertRaises(HTTPException) as falha:
            cadastrar(dados(cpf="98765432101", telefone="47900000002", email="MARIA@CADASTRO.EXAMPLE.COM"))
        self.assertEqual(falha.exception.status_code, 409)


class ValidacaoTests(unittest.TestCase):
    def test_dados_invalidos_sao_rejeitados(self):
        for campo, valor in (
            ("nome", "   "),
            ("cpf", "123"),
            ("cpf", "abcdefghijk"),
            ("telefone", "123"),
            ("email", "sem-arroba"),
            ("email", "a@b"),
            ("email", "a..b@example.com"),
            ("email", "a@-dominio.com"),
            ("senha", "curta"),
            ("senha", "á" * 37),  # 74 bytes, acima do limite do bcrypt
        ):
            with self.subTest(campo=campo, valor=valor):
                with self.assertRaises(ValidationError):
                    dados(**{campo: valor})

    def test_senha_no_limite_de_72_bytes_e_aceita(self):
        self.assertEqual(len(dados(senha="a" * 72).senha), 72)

    def test_erros_de_validacao_tem_formato_claro(self):
        with self.assertRaises(ValidationError) as falha:
            CadastroEntrada(nome="Maria", cpf="123", telefone="47900000001", email="x")
        erros = [{**erro, "loc": ("body", *erro["loc"])} for erro in falha.exception.errors()]
        resposta = asyncio.run(erro_validacao(None, RequestValidationError(erros)))
        corpo = json.loads(resposta.body)
        self.assertEqual(resposta.status_code, 422)
        mensagens = {item["campo"]: item["mensagem"] for item in corpo["detail"]}
        self.assertEqual(mensagens["cpf"], "O CPF deve ter 11 dígitos.")
        self.assertEqual(mensagens["email"], "Informe um e-mail válido.")
        self.assertEqual(mensagens["senha"], "Campo obrigatório.")


if __name__ == "__main__":
    unittest.main()
