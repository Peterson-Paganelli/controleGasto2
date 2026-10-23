import os
import unittest
from decimal import Decimal

from fastapi.testclient import TestClient

from app.auth import criar_token
from app.database import connect, migrate
from app.main import app
from app.senhas import gerar_hash

DOMINIO = "%@isolamento.example.com"
GASTO = {"valor": "19.90", "data": "2026-10-20", "descricao": "Almoço"}
ALTERADO = {"valor": "5.50", "data": "2026-10-21", "descricao": "Café alterado"}


def limpar() -> None:
    # Os registros são criados pela API (que confirma a transação); por isso a limpeza explícita.
    with connect() as conexao:
        conexao.execute(
            "DELETE FROM public.tabela_gastos WHERE id_dadospessoal IN "
            "(SELECT id_dadopessoal FROM public.dados_pessoal WHERE email LIKE %s)",
            (DOMINIO,),
        )
        conexao.execute("DELETE FROM public.dados_pessoal WHERE email LIKE %s", (DOMINIO,))


def criar_usuario(numero: int) -> int:
    with connect() as conexao:
        return conexao.execute(
            "INSERT INTO public.dados_pessoal (nome, cpf, numero_telefone, email, senha) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id_dadopessoal",
            (
                f"Usuário {numero}",
                f"5550000000{numero}",
                f"4795550000{numero}",
                f"usuario{numero}@isolamento.example.com",
                gerar_hash("senha-de-teste"),
            ),
        ).fetchone()[0]


class IsolamentoDeGastosTests(unittest.TestCase):
    """Usuário A e usuário B usam o mesmo recurso, com banco e autenticação reais."""

    @classmethod
    def setUpClass(cls):
        if not os.getenv("POSTGRES_DB", "").endswith("_test"):
            raise RuntimeError("Execute os testes em um banco com sufixo _test.")
        migrate()

    def setUp(self):
        limpar()
        self.addCleanup(limpar)
        self.client = TestClient(app)
        self.id_a, self.id_b = criar_usuario(1), criar_usuario(2)
        self.a = {"Authorization": f"Bearer {criar_token(self.id_a)}"}
        self.b = {"Authorization": f"Bearer {criar_token(self.id_b)}"}

    def criar_gasto(self, headers, corpo=None) -> dict:
        resposta = self.client.post("/gastos", json=corpo or GASTO, headers=headers)
        self.assertEqual(resposta.status_code, 201, resposta.text)
        return resposta.json()

    def descricoes(self, headers) -> list[str]:
        resposta = self.client.get("/gastos", headers=headers)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        return [gasto["descricao"] for gasto in resposta.json()]

    def test_sem_autenticacao_nao_ha_acesso(self):
        gasto = self.criar_gasto(self.a)
        caminho = f"/gastos/{gasto['id']}"
        rotas = [
            ("GET", "/gastos"),
            ("POST", "/gastos"),
            ("GET", caminho),
            ("PUT", caminho),
            ("DELETE", caminho),
        ]
        credenciais = [
            {},
            {"Authorization": "Bearer token-invalido"},
            {"Authorization": "Basic abc"},
        ]
        for metodo, rota in rotas:
            for headers in credenciais:
                with self.subTest(rota=f"{metodo} {rota}", headers=headers):
                    corpo = ALTERADO if metodo in ("POST", "PUT") else None
                    resposta = self.client.request(metodo, rota, json=corpo, headers=headers)
                    self.assertEqual(resposta.status_code, 401)
        # Nada foi criado, alterado ou excluído pelas tentativas sem autenticação.
        resposta = self.client.get(caminho, headers=self.a)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["descricao"], "Almoço")
        self.assertEqual(self.descricoes(self.a), ["Almoço"])

    def test_listagem_mostra_somente_gastos_do_proprio_usuario(self):
        self.criar_gasto(self.a, {**GASTO, "descricao": "A1"})
        self.criar_gasto(self.a, {**GASTO, "descricao": "A2"})
        self.criar_gasto(self.b, {**GASTO, "descricao": "B1"})
        self.assertCountEqual(self.descricoes(self.a), ["A1", "A2"])
        self.assertEqual(self.descricoes(self.b), ["B1"])

    def test_usuario_b_nao_visualiza_altera_nem_exclui_registro_de_a(self):
        gasto = self.criar_gasto(self.a)
        caminho = f"/gastos/{gasto['id']}"
        inexistente = self.client.get("/gastos/2147483647", headers=self.b)

        tentativas = {
            "visualizar": self.client.get(caminho, headers=self.b),
            "alterar": self.client.put(caminho, json=ALTERADO, headers=self.b),
            "excluir": self.client.delete(caminho, headers=self.b),
        }
        for nome, resposta in tentativas.items():
            with self.subTest(operacao=nome):
                self.assertEqual(resposta.status_code, 404)
                # Mesma resposta de um registro inexistente: não revela que o registro existe.
                self.assertEqual(resposta.json(), inexistente.json())

        # O registro de A continua intacto.
        resposta = self.client.get(caminho, headers=self.a)
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertEqual(Decimal(str(corpo["valor"])), Decimal("19.90"))
        self.assertEqual(corpo["data"], "2026-10-20")
        self.assertEqual(corpo["descricao"], "Almoço")

    def test_proprietario_visualiza_altera_e_exclui(self):
        gasto = self.criar_gasto(self.a)
        caminho = f"/gastos/{gasto['id']}"
        self.assertEqual(self.client.get(caminho, headers=self.a).json()["id"], gasto["id"])

        resposta = self.client.put(caminho, json=ALTERADO, headers=self.a)
        self.assertEqual(resposta.status_code, 200)
        corpo = self.client.get(caminho, headers=self.a).json()
        self.assertEqual(Decimal(str(corpo["valor"])), Decimal("5.50"))
        self.assertEqual(corpo["descricao"], "Café alterado")

        resposta = self.client.delete(caminho, headers=self.a)
        self.assertEqual(resposta.status_code, 204)
        self.assertEqual(self.client.get(caminho, headers=self.a).status_code, 404)

    def test_dono_vem_do_token_e_nao_do_corpo(self):
        # B tenta criar um gasto "em nome" de A enviando o ID de A no corpo.
        corpo = {**GASTO, "descricao": "Forjado", "id_dadospessoal": self.id_a, "usuario_id": self.id_a}
        self.criar_gasto(self.b, corpo)
        self.assertEqual(self.descricoes(self.b), ["Forjado"])
        self.assertEqual(self.descricoes(self.a), [])

    def test_exclusao_de_a_nao_afeta_gasto_de_mesmo_valor_de_b(self):
        gasto_a = self.criar_gasto(self.a)
        self.criar_gasto(self.b)
        self.assertEqual(self.client.delete(f"/gastos/{gasto_a['id']}", headers=self.a).status_code, 204)
        self.assertEqual(self.descricoes(self.a), [])
        self.assertEqual(self.descricoes(self.b), ["Almoço"])

    def test_dados_invalidos_retornam_422_e_nao_criam_registro(self):
        invalidos = [
            {**GASTO, "valor": "0"},
            {**GASTO, "valor": "-5"},
            {**GASTO, "valor": "abc"},
            {**GASTO, "valor": "10.999"},
            {**GASTO, "descricao": "   "},
            {**GASTO, "data": "2026-13-40"},
            {"valor": "10.00", "data": "2026-10-20"},
        ]
        for corpo in invalidos:
            with self.subTest(corpo=corpo):
                resposta = self.client.post("/gastos", json=corpo, headers=self.a)
                self.assertEqual(resposta.status_code, 422)
        self.assertEqual(self.descricoes(self.a), [])

    def test_identificador_invalido_retorna_422(self):
        for identificador in ("abc", "0", "99999999999"):
            with self.subTest(identificador=identificador):
                resposta = self.client.get(f"/gastos/{identificador}", headers=self.a)
                self.assertEqual(resposta.status_code, 422)


if __name__ == "__main__":
    unittest.main()
