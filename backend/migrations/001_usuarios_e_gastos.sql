CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE public.dados_pessoal (
    id_dadopessoal serial PRIMARY KEY,
    nome varchar NOT NULL CHECK (btrim(nome) <> ''),
    cpf varchar(11) NOT NULL UNIQUE CHECK (cpf ~ '^[0-9]{11}$'),
    numero_telefone varchar NOT NULL UNIQUE CHECK (btrim(numero_telefone) <> ''),
    email varchar NOT NULL UNIQUE
        CHECK (email = lower(btrim(email)) AND email <> ''),
    -- A procedure de criação recebe a senha e armazena somente o hash bcrypt.
    senha varchar NOT NULL CHECK (senha ~ '^\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}$')
);

CREATE TABLE public.tabela_gastos (
    id_gastos serial PRIMARY KEY,
    id_dadospessoal integer NOT NULL,
    valor numeric(14, 2) NOT NULL CHECK (valor > 0),
    data_tabela date NOT NULL,
    descricao text NOT NULL CHECK (btrim(descricao) <> ''),
    CONSTRAINT fk_dadospessoal FOREIGN KEY (id_dadospessoal)
        REFERENCES public.dados_pessoal (id_dadopessoal)
);

CREATE INDEX tabela_gastos_usuario_data_idx
    ON public.tabela_gastos (id_dadospessoal, data_tabela);

CREATE PROCEDURE public.p_criacaodeconta(
    p_nome varchar,
    p_cpf varchar,
    p_numero_telefone varchar,
    p_email varchar,
    p_senha varchar
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_senha IS NULL OR octet_length(p_senha) NOT BETWEEN 1 AND 72 THEN
        RAISE EXCEPTION 'A senha deve conter entre 1 e 72 bytes.'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.dados_pessoal (nome, cpf, numero_telefone, email, senha)
    VALUES (
        btrim(p_nome), p_cpf, btrim(p_numero_telefone), lower(btrim(p_email)),
        public.crypt(p_senha, public.gen_salt('bf', 12))
    );
END;
$$;

CREATE FUNCTION public.validador_senhaeemail(p_email varchar, p_senha varchar)
RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_senha IS NULL OR octet_length(p_senha) NOT BETWEEN 1 AND 72 THEN
        RETURN false;
    END IF;

    RETURN EXISTS (
        SELECT 1 FROM public.dados_pessoal
        WHERE email = lower(btrim(p_email))
          AND senha = public.crypt(p_senha, senha)
    );
END;
$$;

CREATE PROCEDURE public.p_adicaotabelagastos(
    p_id_dadospessoal integer,
    p_valor numeric,
    p_data_tabela date,
    p_descricao text
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO public.tabela_gastos (id_dadospessoal, valor, data_tabela, descricao)
    VALUES (p_id_dadospessoal, p_valor, p_data_tabela, p_descricao);
END;
$$;

CREATE PROCEDURE public.p_excluirtabelagastos(
    p_id_gastos integer,
    p_id_dadospessoal integer
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM public.tabela_gastos
    WHERE id_gastos = p_id_gastos AND id_dadospessoal = p_id_dadospessoal;
END;
$$;
