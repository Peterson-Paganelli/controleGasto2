create table recorrencias(
	id_recorrencias serial primary key not null,
	valor numeric(14, 2) not null check(0 < valor),
	categoria varchar(100) NOT NULL CHECK (btrim(categoria) <> ''),
	primeiro_vencimento date not null,
	usuario_id int not null,
	
	foreign key (usuario_id) references dados_pessoal(id_dadopessoal)
);

alter table public.tabela_gastos
    add mes_referencia date,
    add recorrencia_id integer,
    add constraint fk_gastos_recorrencia
        foreign key (recorrencia_id) references public.recorrencias (id_recorrencias),
    add constraint ck_gastos_recorrencia_mes
        check (
            recorrencia_id is null
            or (
                mes_referencia is not null
                and extract(day from mes_referencia) = 1
            )
        ),
    add constraint uq_gastos_recorrencia_mes
        unique (recorrencia_id, mes_referencia);




-- Teste de integração das despesas recorrentes.
-- Verifica se a mesma recorrência aceita lançamentos em meses diferentes,
-- bloqueia duplicidade no mesmo mês e rejeita ciclos ausentes ou inválidos.
-- Também verifica se o banco impede excluir uma recorrência com gastos vinculados.
-- O ROLLBACK final desfaz os registros de teste.

BEGIN;

DO $$
DECLARE
    usuario_teste integer;
    recorrencia_teste integer;
    gasto_novembro integer;
    restricao text;
    teste record;
BEGIN
    -- Ordem: ID, nome, CPF, telefone, e-mail, senha.
    INSERT INTO public.dados_pessoal
    VALUES (
        DEFAULT,
        'Usuário de teste',
        '12345678909',
        '11900000000',
        'teste.recorrencia@example.com',
        '$2a$12$R9h/cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jWMUW'
    )
    RETURNING id_dadopessoal INTO usuario_teste;

    INSERT INTO public.recorrencias
        (valor, categoria, primeiro_vencimento, usuario_id)
    VALUES
        (49.90, 'Teste recorrência', DATE '2026-11-15', usuario_teste)
    RETURNING id_recorrencias INTO recorrencia_teste;

    INSERT INTO public.tabela_gastos
        (id_dadospessoal, valor, data_tabela, descricao, categoria,
         vencimento, mes_referencia, recorrencia_id)
    VALUES
        (usuario_teste, 49.90, DATE '2026-11-15', 'Teste novembro',
         'Teste recorrência', DATE '2026-11-15',
         DATE '2026-11-01', recorrencia_teste)
    RETURNING id_gastos INTO gasto_novembro;

    INSERT INTO public.tabela_gastos
        (id_dadospessoal, valor, data_tabela, descricao, categoria,
         vencimento, mes_referencia, recorrencia_id)
    VALUES
        (usuario_teste, 49.90, DATE '2026-12-15', 'Teste dezembro',
         'Teste recorrência', DATE '2026-12-15',
         DATE '2026-12-01', recorrencia_teste);

    FOR teste IN
        SELECT *
        FROM (VALUES
            (DATE '2026-12-01', 'uq_gastos_recorrencia_mes'),
            (NULL::date,       'ck_gastos_recorrencia_mes'),
            (DATE '2026-11-15', 'ck_gastos_recorrencia_mes')
        ) AS casos(mes, restricao_esperada)
    LOOP
        BEGIN
            UPDATE public.tabela_gastos
            SET mes_referencia = teste.mes
            WHERE id_gastos = gasto_novembro;

            RAISE EXCEPTION 'O banco aceitou um ciclo inválido ou duplicado (%).', teste.mes;
        EXCEPTION
            WHEN unique_violation OR check_violation THEN
                GET STACKED DIAGNOSTICS restricao = CONSTRAINT_NAME;

                IF restricao IS DISTINCT FROM teste.restricao_esperada THEN
                    RAISE;
                END IF;
        END;
    END LOOP;

    BEGIN
        DELETE FROM public.recorrencias
        WHERE id_recorrencias = recorrencia_teste;

        RAISE EXCEPTION 'O banco permitiu excluir uma recorrência com gastos vinculados.';
    EXCEPTION
        WHEN foreign_key_violation THEN
            GET STACKED DIAGNOSTICS restricao = CONSTRAINT_NAME;

            IF restricao IS DISTINCT FROM 'fk_gastos_recorrencia' THEN
                RAISE;
            END IF;
    END;

    RAISE NOTICE 'Testes de recorrência passaram';
END $$;

ROLLBACK;



