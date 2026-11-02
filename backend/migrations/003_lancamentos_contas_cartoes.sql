CREATE TABLE public.contas (
    id serial PRIMARY KEY,
    usuario_id integer NOT NULL REFERENCES public.dados_pessoal(id_dadopessoal),
    banco varchar(100) NOT NULL CHECK (btrim(banco) <> ''),
    agencia varchar(30) NOT NULL CHECK (btrim(agencia) <> ''),
    numero varchar(30) NOT NULL CHECK (btrim(numero) <> ''),
    UNIQUE (usuario_id, agencia, numero),
    UNIQUE (id, usuario_id)
);

CREATE TABLE public.cartoes (
    id serial PRIMARY KEY,
    usuario_id integer NOT NULL REFERENCES public.dados_pessoal(id_dadopessoal),
    nome varchar(100) NOT NULL CHECK (btrim(nome) <> ''),
    dia_fechamento integer NOT NULL CHECK (dia_fechamento BETWEEN 1 AND 31),
    conta_id integer,
    FOREIGN KEY (conta_id, usuario_id) REFERENCES public.contas(id, usuario_id),
    UNIQUE (id, usuario_id)
);

CREATE TABLE public.entradas (
    id serial PRIMARY KEY,
    usuario_id integer NOT NULL REFERENCES public.dados_pessoal(id_dadopessoal),
    valor numeric(14, 2) NOT NULL CHECK (valor > 0),
    data date NOT NULL,
    descricao text NOT NULL CHECK (btrim(descricao) <> ''),
    conta_id integer,
    cartao_id integer,
    FOREIGN KEY (conta_id, usuario_id) REFERENCES public.contas(id, usuario_id),
    FOREIGN KEY (cartao_id, usuario_id) REFERENCES public.cartoes(id, usuario_id)
);
CREATE INDEX entradas_usuario_data_idx ON public.entradas(usuario_id, data);

-- O padrão preserva os gastos cadastrados na Sprint 1.
ALTER TABLE public.tabela_gastos
    ADD COLUMN categoria varchar(100) NOT NULL DEFAULT 'Outros' CHECK (btrim(categoria) <> ''),
    ADD COLUMN vencimento date,
    ADD COLUMN conta_id integer,
    ADD COLUMN cartao_id integer,
    ADD FOREIGN KEY (conta_id, id_dadospessoal) REFERENCES public.contas(id, usuario_id),
    ADD FOREIGN KEY (cartao_id, id_dadospessoal) REFERENCES public.cartoes(id, usuario_id);
