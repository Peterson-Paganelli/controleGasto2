import os
import unittest
from decimal import Decimal
from unittest.mock import patch

import psycopg
from fastapi import HTTPException

from app.database import connect, migrate
from app.main import health


class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("POSTGRES_DB", "").endswith("_test"):
            raise RuntimeError("Execute os testes em um banco com sufixo _test.")
        migrate()

    def setUp(self):
        self.connection = connect()
        self.addCleanup(self.connection.close)
        self.addCleanup(self.connection.rollback)

    def create_account(self, cpf="12345678901", phone="47900000001", email="TESTE@EXAMPLE.COM"):
        self.connection.execute(
            "CALL public.p_criacaodeconta(%s, %s, %s, %s, %s)",
            ("Teste", cpf, phone, email, "senha-de-teste"),
        )
        return self.connection.execute(
            "SELECT id_dadopessoal FROM public.dados_pessoal WHERE cpf = %s", (cpf,)
        ).fetchone()[0]

    def test_migration_can_run_twice(self):
        migrate()
        migrate()
        rows = self.connection.execute(
            "SELECT version FROM public.schema_migrations"
        ).fetchall()
        self.assertEqual(rows, [("001_usuarios_e_gastos.sql",)])

    def test_account_and_login(self):
        self.create_account()
        email, password_hash = self.connection.execute(
            "SELECT email, senha FROM public.dados_pessoal"
        ).fetchone()
        self.assertEqual(email, "teste@example.com")
        self.assertNotEqual(password_hash, "senha-de-teste")
        for email_input, password, expected in (
            (" TESTE@EXAMPLE.COM ", "senha-de-teste", True),
            ("teste@example.com", "errada", False),
            ("ausente@example.com", "senha-de-teste", False),
            ("teste@example.com", None, False),
            ("teste@example.com", "a" * 73, False),
        ):
            result = self.connection.execute(
                "SELECT public.validador_senhaeemail(%s, %s)", (email_input, password)
            ).fetchone()[0]
            self.assertEqual(result, expected)

    def test_account_constraints(self):
        self.create_account()
        for cpf, phone, email in (
            ("12345678901", "47900000002", "outro@example.com"),
            ("12345678902", "47900000001", "outro@example.com"),
            ("12345678902", "47900000002", "TESTE@EXAMPLE.COM"),
        ):
            with self.assertRaises(psycopg.errors.UniqueViolation):
                with self.connection.transaction():
                    self.create_account(cpf, phone, email)
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.connection.transaction():
                self.create_account("invalido", "47900000002", "outro@example.com")
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            with self.connection.transaction():
                self.connection.execute(
                    "CALL public.p_criacaodeconta(%s, %s, %s, %s, %s)",
                    ("Teste", "12345678902", "47900000002", "outro@example.com", "á" * 37),
                )

    def test_expense_amount_and_owner(self):
        owner = self.create_account()
        other = self.create_account("12345678902", "47900000002", "outro@example.com")
        self.connection.execute(
            "CALL public.p_adicaotabelagastos(%s, %s, %s, %s)",
            (owner, Decimal("19.90"), "2026-10-12", "Almoço"),
        )
        expense_id, amount = self.connection.execute(
            "SELECT id_gastos, valor FROM public.tabela_gastos"
        ).fetchone()
        self.assertEqual(amount, Decimal("19.90"))
        self.connection.execute("CALL public.p_excluirtabelagastos(%s, %s)", (expense_id, other))
        self.assertEqual(self.connection.execute("SELECT count(*) FROM public.tabela_gastos").fetchone()[0], 1)
        self.connection.execute("CALL public.p_excluirtabelagastos(%s, %s)", (expense_id, owner))
        self.assertEqual(self.connection.execute("SELECT count(*) FROM public.tabela_gastos").fetchone()[0], 0)
        for user_id, amount, error in (
            (owner, "-1", psycopg.errors.CheckViolation),
            (owner, "0", psycopg.errors.CheckViolation),
            (-1, "10", psycopg.errors.ForeignKeyViolation),
        ):
            with self.assertRaises(error):
                with self.connection.transaction():
                    self.connection.execute(
                        "CALL public.p_adicaotabelagastos(%s, %s, %s, %s)",
                        (user_id, Decimal(amount), "2026-10-12", "Teste"),
                    )

    def test_health_checks_database(self):
        self.assertEqual(health(), {"status": "ok"})
        with patch("app.main.connect", side_effect=psycopg.OperationalError("offline")):
            with self.assertRaises(HTTPException) as failure:
                health()
        self.assertEqual(failure.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
