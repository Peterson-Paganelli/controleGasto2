from fastapi import HTTPException


def validar_vinculos(conexao, usuario_id: int, conta_id: int | None, cartao_id: int | None = None):
    """Não permite associar um lançamento aos cadastros de outra pessoa."""
    for tabela, campo, identificador in (
        ("contas", "conta_id", conta_id),
        ("cartoes", "cartao_id", cartao_id),
    ):
        if identificador is None:
            continue
        registro = conexao.execute(
            f"SELECT id FROM public.{tabela} WHERE id = %s AND usuario_id = %s",
            (identificador, usuario_id),
        ).fetchone()
        if registro is None:
            raise HTTPException(status_code=422, detail=[{
                "campo": campo, "mensagem": "Selecione um cadastro da sua conta."
            }])
