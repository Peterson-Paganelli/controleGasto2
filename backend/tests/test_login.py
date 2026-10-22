import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import jwt
import psycopg
from fastapi.testclient import TestClient

from app.auth import JWT_SECRET, criar_token
from app.main import app

LOGIN = {"email": "  MARIA@EXAMPLE.COM ", "senha": "senha-de-teste"}


class LoginTests(unittest.TestCase):
    def setUp(self):
        # O banco é simulado; as rotas, dependências e tokens são reais.
        self.client = TestClient(app)
        conectar = patch("app.main.connect")
        self.banco = conectar.start().return_value.__enter__.return_value
        self.addCleanup(conectar.stop)
        conectar_auth = patch("app.auth.connect")
        conectar_auth.start().return_value.__enter__.return_value = self.banco
        self.addCleanup(conectar_auth.stop)
        verificar = patch("app.main.verificar_senha", return_value=True)
        self.verificar = verificar.start()
        self.addCleanup(verificar.stop)
        self.banco.execute.return_value.fetchone.return_value = (7, "hash-armazenado")
        self.sessoes = {}
        self.banco.execute.side_effect = self.executar

    def executar(self, sql, dados=()):
        if sql.startswith("INSERT INTO public.sessoes"):
            self.sessoes[dados[0]] = dados[1]
        elif sql == "DELETE FROM public.sessoes WHERE id = %s":
            self.sessoes.pop(dados[0], None)
        elif "JOIN public.sessoes" in sql and self.sessoes.get(dados[1]) != dados[0]:
            cursor = Mock()
            cursor.fetchone.return_value = None
            return cursor
        return self.banco.execute.return_value

    def test_login_valido_verifica_bcrypt_e_emite_token(self):
        resposta = self.client.post("/login", json=LOGIN)
        self.assertEqual(resposta.status_code, 200)
        self.verificar.assert_called_once_with(LOGIN["senha"], "hash-armazenado")
        self.assertEqual(self.banco.execute.call_args_list[0].args[1], ("maria@example.com",))
        corpo = resposta.json()
        self.assertEqual(set(corpo), {"access_token", "token_type"})
        self.assertEqual(corpo["token_type"], "bearer")
        dados = jwt.decode(corpo["access_token"], JWT_SECRET, algorithms=["HS256"])
        self.assertEqual(set(dados), {"sub", "jti", "exp"})
        self.assertEqual(dados["sub"], "7")
        self.assertEqual(self.sessoes[dados["jti"]], 7)
        self.assertAlmostEqual(dados["exp"] - datetime.now(timezone.utc).timestamp(), 1800, delta=5)

    def test_login_rejeita_senha_incorreta_e_usuario_inexistente(self):
        self.verificar.return_value = False
        for linha in ((7, "hash-armazenado"), None):
            with self.subTest(usuario=linha):
                self.banco.execute.return_value.fetchone.return_value = linha
                resposta = self.client.post("/login", json=LOGIN)
                self.assertEqual(resposta.status_code, 401)
                self.assertEqual(resposta.json()["detail"], "E-mail ou senha inválidos.")

    def test_token_do_login_permite_acesso_a_rota_protegida(self):
        token = self.client.post("/login", json=LOGIN).json()["access_token"]
        self.banco.execute.return_value.fetchone.return_value = (7, "Maria", "maria@example.com")
        resposta = self.client.get("/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"id": 7, "nome": "Maria", "email": "maria@example.com"})

    def test_rota_rejeita_autenticacao_ausente_ou_esquema_incorreto(self):
        for headers in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}):
            with self.subTest(headers=headers):
                resposta = self.client.get("/me", headers=headers)
                self.assertEqual(resposta.status_code, 401)
                self.assertEqual(resposta.headers["WWW-Authenticate"], "Bearer")
        self.banco.execute.assert_not_called()

    def test_rota_rejeita_tokens_invalidos_ou_expirados(self):
        futuro = datetime.now(timezone.utc) + timedelta(minutes=30)
        tokens = [
            "token-invalido",
            jwt.encode({"sub": "7", "jti": "teste", "exp": futuro}, "outra-chave-aleatoria-com-32-bytes", algorithm="HS256"),
            jwt.encode({"sub": "7", "jti": "teste", "exp": 0}, JWT_SECRET, algorithm="HS256"),
            jwt.encode({"sub": "7", "jti": "teste"}, JWT_SECRET, algorithm="HS256"),
            jwt.encode({"jti": "teste", "exp": futuro}, JWT_SECRET, algorithm="HS256"),
            jwt.encode({"sub": "7", "exp": futuro}, JWT_SECRET, algorithm="HS256"),
            jwt.encode({"sub": "invalido", "jti": "teste", "exp": futuro}, JWT_SECRET, algorithm="HS256"),
            jwt.encode({"sub": "7", "jti": "teste", "exp": futuro}, JWT_SECRET, algorithm="HS384"),
        ]
        for token in tokens:
            with self.subTest(token=token):
                resposta = self.client.get("/me", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(resposta.status_code, 401)
        self.banco.execute.assert_not_called()

    def test_identifica_o_usuario_em_cada_requisicao(self):
        for usuario_id in (7, 8):
            with self.subTest(usuario_id=usuario_id):
                self.banco.execute.return_value.fetchone.return_value = (
                    usuario_id, "Teste", f"teste{usuario_id}@example.com"
                )
                token = criar_token(usuario_id)
                resposta = self.client.get("/me", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.json()["id"], usuario_id)
                self.assertEqual(self.banco.execute.call_args.args[1][0], usuario_id)
        consultas = [chamada for chamada in self.banco.execute.call_args_list if "JOIN public.sessoes" in chamada.args[0]]
        self.assertEqual(len(consultas), 2)

    def test_rota_rejeita_usuario_removido(self):
        self.banco.execute.return_value.fetchone.return_value = None
        resposta = self.client.get("/me", headers={"Authorization": f"Bearer {criar_token(7)}"})
        self.assertEqual(resposta.status_code, 401)

    def test_banco_indisponivel_retorna_503(self):
        token = criar_token(7)
        self.banco.execute.side_effect = psycopg.OperationalError("offline")
        self.assertEqual(self.client.post("/login", json=LOGIN).status_code, 503)
        resposta = self.client.get("/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resposta.status_code, 503)

    def test_logout_impede_reuso_do_token_sem_encerrar_outra_sessao(self):
        primeiro = criar_token(7)
        segundo = criar_token(7)
        self.assertNotEqual(primeiro, segundo)
        self.banco.execute.return_value.fetchone.return_value = (7, "Maria", "maria@example.com")
        headers = {"Authorization": f"Bearer {primeiro}"}
        self.assertEqual(self.client.get("/me", headers=headers).status_code, 200)
        resposta = self.client.post("/logout", headers=headers)
        self.assertEqual(resposta.status_code, 204)
        self.assertEqual(resposta.content, b"")
        self.assertEqual(self.client.get("/me", headers=headers).status_code, 401)
        self.assertEqual(self.client.post("/logout", headers=headers).status_code, 401)
        resposta = self.client.get("/me", headers={"Authorization": f"Bearer {segundo}"})
        self.assertEqual(resposta.status_code, 200)

    def test_logout_exige_autenticacao(self):
        self.assertEqual(self.client.post("/logout").status_code, 401)
        self.banco.execute.assert_not_called()

    def test_token_sem_sessao_ativa_e_rejeitado(self):
        token = jwt.encode(
            {"sub": "7", "jti": "sessao-inexistente", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
            JWT_SECRET, algorithm="HS256",
        )
        resposta = self.client.get("/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resposta.status_code, 401)

    def test_falha_ao_salvar_sessao_nao_permite_login(self):
        with patch("app.auth.connect", side_effect=psycopg.OperationalError("offline")):
            self.assertEqual(self.client.post("/login", json=LOGIN).status_code, 503)


if __name__ == "__main__":
    unittest.main()
