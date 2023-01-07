CREATE TABLE
  public.events (
    id character(8) NOT NULL,
    title character varying(255) NOT NULL,
    start timestamp
    with
      time zone NOT NULL,
      "end" timestamp
    with
      time zone NOT NULL,
      "limit" smallint NULL,
      reserved smallint NULL
  );

ALTER TABLE
  public.events
ADD
  CONSTRAINT events_pkey PRIMARY KEY (id)