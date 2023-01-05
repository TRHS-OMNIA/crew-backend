CREATE TABLE
  public.users (
    id character varying(32) NOT NULL,
    last_name character varying(255) NOT NULL,
    first_name character varying(255) NOT NULL,
    nickname character varying(255) NULL,
    grade smallint NOT NULL,
    period smallint NOT NULL,
    class character varying(32) NOT NULL
  );

ALTER TABLE
  public.users
ADD
  CONSTRAINT users_pkey PRIMARY KEY (id)