CREATE TABLE public.sessoes (
    id text PRIMARY KEY,
    usuario_id integer NOT NULL REFERENCES public.dados_pessoal (id_dadopessoal) ON DELETE CASCADE,
    expira_em timestamptz NOT NULL
);
