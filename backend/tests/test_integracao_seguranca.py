"""S1-10: testes de integração de autenticação e segurança.

Usam a API real (TestClient) com PostgreSQL real: cadastro, login, BCrypt, acesso
sem autenticação e isolamento entre usuários, sem simular banco nem senhas.
"""

import base64
import json
import os
import re
import unittest
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient

from app.auth import JWT_SECRET
from app.database import connect, migrate
from app.main import app
from app.senhas import CUSTO_MINIMO, custo_do_hash, verificar_senha

DOMINIO = "%@seguranca.example.com"
SENHA = "senha-de-teste"
MENSAGEM_LOGIN_INVALIDO = "E-mail ou senha inválidos."
GASTO = {"valor": "19.90", "data": "2026-10-20", "descricao": "Almoço"}
# Rotas abertas de propósito. Qualquer outra rota nova precisa exigir autenticação.
ROTAS_PUBLICAS = {("GET", "/health"), ("POST", "/cadastro"), ("POST", "/login")}


def limpar() -> None:
    # A API confirma as transações, então os registros criados precisam ser removidos.
    with connect() as conexao:
        conexao.execute(
            "DELETE FROM public.tabela_gastos WHERE id_dadospessoal IN "
            "(SELECT id_dadopessoal FROM public.dados_pessoal WHERE email LIKE %s)",
            (DOMINIO,),
        )
        conexao.execute("DELETE FROM public.dados_pessoal WHERE email LIKE %s", (DOMINIO,))


def consultar(sql: str, dados: tuple = ()):
    with connect() as conexao:
        return conexao.execute(sql, dados).fetchall()


class IntegracaoSegurancaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("POSTGRES_DB", "").endswith("_test"):
            raise RuntimeError("Execute os testes em um banco com sufixo _test.")
        migrate()

    def setUp(self):
        limpar()
        self.addCleanup(limpar)
        self.client = TestClient(app)

    # ---------- auxiliares ----------
    def email(self, numero: int) -> str:
        return f"usuario{numero}@seguranca.example.com"

    def registrar(self, numero: int, senha: str = SENHA, **alteracoes):
        corpo = {
            "nome": f"Usuário {numero}",
            "cpf": f"4440000000{numero}",
            "telefone": f"4794440000{numero}",
            "email": self.email(numero),
            "senha": senha,
            **alteracoes,
        }
        return self.client.post("/cadastro", json=corpo)

    def entrar(self, numero: int, senha: str = SENHA):
        return self.client.post("/login", json={"email": self.email(numero), "senha": senha})

    def autenticar(self, numero: int) -> tuple[dict, int, str]:
        """Cadastra e faz login pela API. Retorna (headers, id do usuário, token)."""
        cadastro = self.registrar(numero)
        self.assertEqual(cadastro.status_code, 201, cadastro.text)
        login = self.entrar(numero)
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, cadastro.json()["id"], token

    def token_forjado(self, usuario_id, jti, chave=JWT_SECRET, algoritmo="HS256") -> str:
        expira = datetime.now(timezone.utc) + timedelta(minutes=30)
        return jwt.encode(
            {"sub": str(usuario_id), "jti": jti, "exp": expira}, chave, algorithm=algoritmo
        )

    def adulterar_sub(self, token: str, novo_sub: int) -> str:
        """Troca o dono no payload mantendo a assinatura original (assinatura passa a ser inválida)."""
        cabecalho, payload, assinatura = token.split(".")
        dados = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        dados["sub"] = str(novo_sub)
        novo = base64.urlsafe_b64encode(json.dumps(dados).encode()).rstrip(b"=").decode()
        return f"{cabecalho}.{novo}.{assinatura}"

    # ---------- cadastro ----------
    def test_cadastro_duplicado_e_rejeitado(self):
        self.assertEqual(self.registrar(1).status_code, 201)
        # (usuário do cadastro, dados alterados, campo que deve ser apontado como duplicado)
        casos = (
            (1, {"cpf": "44400000099", "telefone": "47944400099"}, "email"),
            (1, {"cpf": "44400000099", "telefone": "47944400099", "email": self.email(1).upper()}, "email"),
            (9, {"cpf": "44400000001"}, "cpf"),
            (9, {"telefone": "47944400001"}, "telefone"),
        )
        for numero, alteracoes, campo in casos:
            with self.subTest(campo=campo, alteracoes=alteracoes):
                resposta = self.registrar(numero, **alteracoes)
                self.assertEqual(resposta.status_code, 409, resposta.text)
                self.assertEqual(resposta.json()["detail"][0]["campo"], campo)
        total = consultar("SELECT count(*) FROM public.dados_pessoal WHERE email LIKE %s", (DOMINIO,))
        self.assertEqual(total[0][0], 1)  # nenhuma tentativa duplicada criou usuário

    def test_cadastro_invalido_retorna_422_e_nao_cria_usuario(self):
        for alteracoes in ({"cpf": "123"}, {"email": "sem-arroba"}, {"senha": "curta"}, {"nome": "  "}):
            with self.subTest(alteracoes=alteracoes):
                self.assertEqual(self.registrar(1, **alteracoes).status_code, 422)
        total = consultar("SELECT count(*) FROM public.dados_pessoal WHERE email LIKE %s", (DOMINIO,))
        self.assertEqual(total[0][0], 0)

    # ---------- BCrypt ----------
    def test_senha_e_gravada_somente_como_hash_bcrypt_com_custo_minimo(self):
        self.assertEqual(self.registrar(1).status_code, 201)
        (hash_gravado,), = consultar(
            "SELECT senha FROM public.dados_pessoal WHERE email = %s", (self.email(1),)
        )
        self.assertNotEqual(hash_gravado, SENHA)
        self.assertNotIn(SENHA, hash_gravado)
        self.assertGreaterEqual(custo_do_hash(hash_gravado), CUSTO_MINIMO)
        self.assertTrue(verificar_senha(SENHA, hash_gravado))
        self.assertFalse(verificar_senha("senha-errada", hash_gravado))
        texto_puro = consultar("SELECT count(*) FROM public.dados_pessoal WHERE senha = %s", (SENHA,))
        self.assertEqual(texto_puro[0][0], 0)

    def test_senha_no_limite_do_bcrypt_nao_e_truncada(self):
        senha = "a" * 72
        self.assertEqual(self.registrar(1, senha=senha).status_code, 201)
        self.assertEqual(self.entrar(1, senha).status_code, 200)
        # O bcrypt ignora o que passa de 72 bytes; a API não pode aceitar essa senha estendida.
        self.assertEqual(self.entrar(1, senha + "x").status_code, 401)
        self.assertEqual(self.registrar(2, senha="a" * 73).status_code, 422)

    # ---------- login ----------
    def test_senha_incorreta_e_rejeitada_sem_revelar_se_o_email_existe(self):
        self.assertEqual(self.registrar(1).status_code, 201)
        senha_errada = self.entrar(1, "senha-errada")
        email_inexistente = self.client.post(
            "/login", json={"email": "ninguem@seguranca.example.com", "senha": SENHA}
        )
        for resposta in (senha_errada, email_inexistente):
            self.assertEqual(resposta.status_code, 401)
            self.assertEqual(resposta.json()["detail"], MENSAGEM_LOGIN_INVALIDO)
            self.assertEqual(resposta.headers["WWW-Authenticate"], "Bearer")
        self.assertEqual(senha_errada.json(), email_inexistente.json())
        self.assertEqual(self.entrar(1, SENHA.upper()).status_code, 401)
        self.assertEqual(self.entrar(1).status_code, 200)

    def test_token_nao_carrega_dados_sensiveis(self):
        _, usuario_id, token = self.autenticar(1)
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        self.assertEqual(set(claims), {"sub", "jti", "exp"})
        self.assertEqual(claims["sub"], str(usuario_id))

    # ---------- acesso sem autenticação ----------
    def test_toda_rota_exige_autenticacao_exceto_as_publicas(self):
        verificadas = 0
        for rota in iter_route_contexts(app.routes):
            if not isinstance(rota.original_route, APIRoute):
                continue
            caminho = re.sub(r"\{[^}]+\}", "1", rota.path)
            for metodo in sorted(rota.methods - {"HEAD", "OPTIONS"}):
                if (metodo, rota.path) in ROTAS_PUBLICAS:
                    continue
                for headers in ({}, {"Authorization": "Bearer token-invalido"}):
                    with self.subTest(rota=f"{metodo} {rota.path}", headers=headers):
                        corpo = {} if metodo in ("POST", "PUT", "PATCH") else None
                        resposta = self.client.request(metodo, caminho, json=corpo, headers=headers)
                        self.assertEqual(
                            resposta.status_code, 401,
                            f"{metodo} {rota.path} deve exigir autenticação. Se a rota for "
                            "pública de propósito, adicione-a a ROTAS_PUBLICAS.",
                        )
                verificadas += 1
        self.assertGreaterEqual(verificadas, 7)  # /me, /logout e as 5 rotas de /gastos

    def test_rotas_publicas_continuam_abertas(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.post("/cadastro", json={}).status_code, 422)
        self.assertEqual(self.client.post("/login", json={}).status_code, 422)

    def test_tokens_invalidos_sao_rejeitados_com_banco_real(self):
        headers_a, id_a, token_a = self.autenticar(1)
        headers_b, id_b, _ = self.autenticar(2)
        jti_a = jwt.decode(token_a, JWT_SECRET, algorithms=["HS256"])["jti"]
        chave_outra = "outra-chave-aleatoria-com-mais-de-32-bytes"
        invalidos = {
            "assinado com outra chave": self.token_forjado(id_a, jti_a, chave_outra),
            "dono trocado sem refazer a assinatura": self.adulterar_sub(token_a, id_b),
            "algoritmo none": self.token_forjado(id_a, jti_a, None, "none"),
            "assinatura válida, mas sessão de outro usuário": self.token_forjado(id_b, jti_a),
            "sessão inexistente": self.token_forjado(id_a, "sessao-inexistente"),
        }
        for nome, token in invalidos.items():
            with self.subTest(token=nome):
                resposta = self.client.get("/me", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(resposta.status_code, 401)
        # Os tokens legítimos seguem valendo e cada um identifica o seu dono.
        self.assertEqual(self.client.get("/me", headers=headers_a).json()["id"], id_a)
        self.assertEqual(self.client.get("/me", headers=headers_b).json()["id"], id_b)

    def test_sessao_expirada_ou_usuario_removido_perde_o_acesso(self):
        headers, usuario_id, _ = self.autenticar(1)
        self.assertEqual(self.client.get("/me", headers=headers).status_code, 200)
        with connect() as conexao:
            conexao.execute(
                "UPDATE public.sessoes SET expira_em = now() - interval '1 minute' "
                "WHERE usuario_id = %s", (usuario_id,),
            )
        self.assertEqual(self.client.get("/me", headers=headers).status_code, 401)
        self.assertEqual(self.client.get("/gastos", headers=headers).status_code, 401)

        novos_headers = {"Authorization": f"Bearer {self.entrar(1).json()['access_token']}"}
        self.assertEqual(self.client.get("/me", headers=novos_headers).status_code, 200)
        limpar()  # remove o usuário e, em cascata, as sessões
        self.assertEqual(self.client.get("/me", headers=novos_headers).status_code, 401)

    def test_logout_invalida_o_token_em_todas_as_rotas(self):
        headers, _, _ = self.autenticar(1)
        self.assertEqual(self.client.post("/logout", headers=headers).status_code, 204)
        for rota in ("/me", "/gastos"):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(rota, headers=headers).status_code, 401)

    # ---------- isolamento entre usuários ----------
    def test_acesso_aos_dados_de_outro_usuario_e_rejeitado(self):
        headers_a, _, _ = self.autenticar(1)
        headers_b, _, _ = self.autenticar(2)
        gasto = self.client.post("/gastos", json=GASTO, headers=headers_a)
        self.assertEqual(gasto.status_code, 201, gasto.text)
        caminho = f"/gastos/{gasto.json()['id']}"

        self.assertEqual(self.client.get("/gastos", headers=headers_b).json(), [])
        tentativas = (
            self.client.get(caminho, headers=headers_b),
            self.client.put(caminho, json={**GASTO, "descricao": "invadido"}, headers=headers_b),
            self.client.delete(caminho, headers=headers_b),
        )
        for resposta in tentativas:
            self.assertEqual(resposta.status_code, 404)
        corpo = self.client.get(caminho, headers=headers_a).json()
        self.assertEqual(corpo["descricao"], "Almoço")

    # ---------- entradas maliciosas ----------
    def test_texto_com_sql_e_tratado_como_dado(self):
        self.assertEqual(self.registrar(1).status_code, 201)
        payloads = ("' OR '1'='1", "x' OR 1=1 --", "admin'--", "'; DROP TABLE dados_pessoal; --")
        for payload in payloads:
            with self.subTest(payload=payload):
                for corpo in (
                    {"email": payload, "senha": SENHA},
                    {"email": self.email(1), "senha": payload},
                    {"email": payload, "senha": payload},
                ):
                    self.assertEqual(self.client.post("/login", json=corpo).status_code, 401)

        nome = "Robert'); DROP TABLE dados_pessoal;--"
        cadastro = self.registrar(2, nome=nome)
        self.assertEqual(cadastro.status_code, 201, cadastro.text)
        token = self.entrar(2).json()["access_token"]
        resposta = self.client.get("/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resposta.json()["nome"], nome)  # gravado como texto, sem executar
        total = consultar("SELECT count(*) FROM public.dados_pessoal WHERE email LIKE %s", (DOMINIO,))
        self.assertEqual(total[0][0], 2)

    # ---------- vazamento de segredos ----------
    def test_respostas_nunca_expoem_senha_nem_hash(self):
        cadastro = self.registrar(1)
        login = self.entrar(1)
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        gasto = self.client.post("/gastos", json=GASTO, headers=headers)
        respostas = [
            cadastro, login, gasto,
            self.client.get("/me", headers=headers),
            self.client.get("/gastos", headers=headers),
            self.client.get(f"/gastos/{gasto.json()['id']}", headers=headers),
        ]
        (hash_gravado,), = consultar(
            "SELECT senha FROM public.dados_pessoal WHERE email = %s", (self.email(1),)
        )
        for resposta in respostas:
            with self.subTest(url=str(resposta.url)):
                self.assertIn(resposta.status_code, (200, 201))
                self.assertNotIn(hash_gravado, resposta.text)
                self.assertNotIn(SENHA, resposta.text)
                self.assertNotIn('"senha"', resposta.text)

    def test_erros_nao_repetem_a_senha_enviada(self):
        secreta = "senha-secreta-unica-9d8f7"
        self.assertEqual(self.registrar(1).status_code, 201)
        respostas = [
            self.registrar(1, senha=secreta),  # 409: e-mail já cadastrado
            self.registrar(2, senha=secreta, cpf="123"),  # 422: CPF inválido
            self.registrar(2, senha="a" * 73),  # 422: senha longa demais
            self.entrar(1, secreta),  # 401
        ]
        for resposta in respostas:
            with self.subTest(status=resposta.status_code):
                self.assertIn(resposta.status_code, (401, 409, 422))
                self.assertNotIn(secreta, resposta.text)
                self.assertNotIn("a" * 73, resposta.text)


if __name__ == "__main__":
    unittest.main()
