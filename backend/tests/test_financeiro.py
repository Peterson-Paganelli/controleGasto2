import os
import unittest

import psycopg
from fastapi.testclient import TestClient

from app.auth import criar_token
from app.database import connect, migrate
from app.main import app
from app.senhas import gerar_hash


class FinanceiroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("POSTGRES_DB", "").endswith("_test"):
            raise RuntimeError("Use um banco com sufixo _test.")
        migrate()

    def setUp(self):
        self.client = TestClient(app)
        self.ids = []
        self.addCleanup(self.limpar)
        for numero in (1, 2):
            with connect() as conexao:
                id = conexao.execute(
                    "INSERT INTO public.dados_pessoal (nome, cpf, numero_telefone, email, senha) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id_dadopessoal",
                    ("Financeiro", f"7770000000{numero}", f"4797770000{numero}",
                     f"pessoa{numero}@financeiro.example.com", gerar_hash("senha-de-teste")),
                ).fetchone()[0]
                self.ids.append(id)
        self.a, self.b = [{"Authorization": f"Bearer {criar_token(id)}"} for id in self.ids]

    def limpar(self):
        with connect() as conexao:
            for tabela, campo in (("entradas", "usuario_id"), ("tabela_gastos", "id_dadospessoal"),
                                  ("cartoes", "usuario_id"), ("contas", "usuario_id"),
                                  ("dados_pessoal", "id_dadopessoal")):
                conexao.execute(f"DELETE FROM public.{tabela} WHERE {campo} = ANY(%s)", (self.ids,))

    def criar(self, rota, corpo, headers=None):
        resposta = self.client.post(rota, json=corpo, headers=headers or self.a)
        self.assertEqual(resposta.status_code, 201, resposta.text)
        return resposta.json()

    def conta(self, headers=None):
        return self.criar("/contas", {"banco": "Banco", "agencia": "001", "numero": "00012-3"}, headers)

    def test_conta_duplicada_por_usuario(self):
        conta = self.conta()
        resposta = self.client.post("/contas", json=conta, headers=self.a)
        self.assertEqual(resposta.status_code, 409)
        self.assertIn("agência e número", resposta.text)
        self.conta(self.b)
        for headers in (self.a, self.b):
            self.assertEqual(len(self.client.get("/contas", headers=headers).json()), 1)

    def test_cartao_limites_e_conta_opcional(self):
        for dia in (1, 31):
            cartao = self.criar("/cartoes", {"nome": "Cartão", "dia_fechamento": dia})
            self.assertIsNone(cartao["conta_id"])
        for dia in (0, 32, 1.5, True):
            resposta = self.client.post("/cartoes", json={"nome": "Cartão", "dia_fechamento": dia}, headers=self.a)
            self.assertEqual(resposta.status_code, 422)
        conta = self.conta()
        self.criar("/cartoes", {"nome": "Vinculado", "dia_fechamento": 10, "conta_id": conta["id"]})
        self.assertEqual(self.client.get("/cartoes", headers=self.b).json(), [])

    def test_entradas_gastos_e_edicao(self):
        conta = self.conta()
        cartao = self.criar("/cartoes", {"nome": "Cartão", "dia_fechamento": 15, "conta_id": conta["id"]})
        dados = {"valor": "19.90", "data": "2026-10-31", "descricao": "Teste",
                 "conta_id": conta["id"], "cartao_id": cartao["id"]}
        entrada = self.criar("/entradas", dados)
        self.assertEqual(entrada["valor"], "19.90")
        gasto = self.criar("/gastos", {**dados, "categoria": "Alimentação", "vencimento": "2026-11-05"})
        self.assertEqual(gasto["categoria"], "Alimentação")
        self.assertEqual(gasto["vencimento"], "2026-11-05")
        self.assertEqual(self.client.get("/entradas", headers=self.b).json(), [])
        self.assertEqual(self.client.get("/gastos", headers=self.b).json(), [])
        rota = f"/gastos/{gasto['id']}"
        for metodo in ("get", "put", "delete"):
            resposta = self.client.request(metodo, rota, headers=self.b, json=dados if metodo == "put" else None)
            self.assertEqual(resposta.status_code, 404)
        atualizado = self.client.put(rota, json={**dados, "categoria": "Transporte"}, headers=self.a)
        self.assertEqual(atualizado.status_code, 200)
        self.assertEqual(atualizado.json()["categoria"], "Transporte")
        self.assertIsNone(atualizado.json()["vencimento"])
        self.assertEqual(self.client.delete(rota, headers=self.a).status_code, 204)

    def test_rejeitar_vinculos_de_outro_usuario(self):
        conta = self.conta(self.b)
        cartao = self.criar("/cartoes", {"nome": "B", "dia_fechamento": 1}, self.b)
        dados = {"descricao": "Inválido", "data": "2026-10-31", "valor": "10.00"}
        for rota in ("/entradas", "/gastos"):
            for vinculo in ({"conta_id": conta["id"]}, {"cartao_id": cartao["id"]}, {"conta_id": 2147483647}):
                resposta = self.client.post(rota, json={**dados, **vinculo}, headers=self.a)
                self.assertEqual(resposta.status_code, 422)
            self.assertEqual(self.client.get(rota, headers=self.a).json(), [])
        resposta = self.client.post("/cartoes", json={"nome": "A", "dia_fechamento": 1, "conta_id": conta["id"]}, headers=self.a)
        self.assertEqual(resposta.status_code, 422)
        # O banco também impede vínculos cruzados, mesmo sem passar pela API.
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with connect() as conexao:
                conexao.execute("INSERT INTO public.cartoes (usuario_id, nome, dia_fechamento, conta_id) VALUES (%s, 'A', 1, %s)", (self.ids[0], conta["id"]))

    def test_validacoes_e_autenticacao(self):
        for rota in ("/entradas", "/gastos", "/contas", "/cartoes"):
            self.assertEqual(self.client.get(rota).status_code, 401)
            self.assertEqual(self.client.post(rota, json={}).status_code, 401)
        for rota in ("/entradas", "/gastos"):
            dados = {"valor": "10.00", "data": "2026-10-31", "descricao": "Teste"}
            for campo, valor in (("valor", "0"), ("valor", "1.999"), ("valor", "NaN"),
                                 ("descricao", "  "), ("data", "2026-02-30")):
                self.assertEqual(self.client.post(rota, json={**dados, campo: valor}, headers=self.a).status_code, 422)
        self.assertEqual(self.client.post("/contas", json={"banco": " ", "agencia": "1", "numero": "2"}, headers=self.a).status_code, 422)
        self.assertEqual(self.client.post("/gastos", json={**dados, "categoria": " "}, headers=self.a).status_code, 422)


if __name__ == "__main__":
    unittest.main()
