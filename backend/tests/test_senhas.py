import os
import unittest

import psycopg

from app.database import connect, migrate
from app.senhas import CUSTO_MINIMO, custo_do_hash, gerar_hash, verificar_senha

SENHA = "senha-de-teste"


class SenhasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("POSTGRES_DB", "").endswith("_test"):
            raise RuntimeError("Execute os testes em um banco com sufixo _test.")
        migrate()

    def test_hash_usa_custo_minimo_10(self):
        hash_gerado = gerar_hash(SENHA)
        self.assertTrue(hash_gerado.startswith("$2"))
        self.assertGreaterEqual(custo_do_hash(hash_gerado), CUSTO_MINIMO)

    def test_hash_nao_contem_a_senha_e_muda_a_cada_geracao(self):
        primeiro, segundo = gerar_hash(SENHA), gerar_hash(SENHA)
        self.assertNotIn(SENHA, primeiro)
        self.assertNotEqual(primeiro, segundo)  # salt aleatório

    def test_senha_correta_e_aceita_e_incorreta_e_rejeitada(self):
        hash_gerado = gerar_hash(SENHA)
        self.assertTrue(verificar_senha(SENHA, hash_gerado))
        self.assertFalse(verificar_senha("senha-errada", hash_gerado))
        self.assertFalse(verificar_senha(SENHA.upper(), hash_gerado))

    def test_custo_abaixo_do_minimo_e_recusado(self):
        for custo in (4, 9, 32):
            with self.subTest(custo=custo):
                with self.assertRaises(ValueError):
                    gerar_hash(SENHA, custo=custo)
        self.assertGreaterEqual(custo_do_hash(gerar_hash(SENHA, custo=10)), 10)

    def test_entradas_invalidas(self):
        for senha in ("", "a" * 73, "á" * 37):
            with self.subTest(senha=len(senha)):
                with self.assertRaises(ValueError):
                    gerar_hash(senha)
        hash_gerado = gerar_hash(SENHA)
        self.assertFalse(verificar_senha("", hash_gerado))
        self.assertFalse(verificar_senha(SENHA, "texto-puro"))
        self.assertFalse(verificar_senha(SENHA, ""))
        with self.assertRaises(ValueError):
            custo_do_hash("texto-puro")

    def test_hash_e_compativel_com_o_login_do_banco(self):
        connection = connect()
        self.addCleanup(connection.close)
        self.addCleanup(connection.rollback)
        connection.execute(
            "INSERT INTO public.dados_pessoal (nome, cpf, numero_telefone, email, senha) "
            "VALUES ('Teste', '11122233344', '47900000009', 'senhas@example.com', %s)",
            (gerar_hash(SENHA),),
        )
        valido = connection.execute(
            "SELECT public.validador_senhaeemail('senhas@example.com', %s)", (SENHA,)
        ).fetchone()[0]
        self.assertTrue(valido)

    def test_banco_recusa_senha_em_texto_puro(self):
        connection = connect()
        self.addCleanup(connection.close)
        self.addCleanup(connection.rollback)
        with self.assertRaises(psycopg.errors.CheckViolation):
            connection.execute(
                "INSERT INTO public.dados_pessoal (nome, cpf, numero_telefone, email, senha) "
                "VALUES ('Teste', '11122233355', '47900000008', 'puro@example.com', %s)",
                (SENHA,),
            )


if __name__ == "__main__":
    unittest.main()
