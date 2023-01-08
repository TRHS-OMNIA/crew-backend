CREATE TABLE
  public.entries (
    uid character varying(32) NOT NULL,
    eid character(8) NOT NULL,
    check_in timestamp
    with
      time zone NULL,
      check_out timestamp
    with
      time zone NULL,
      "position" character varying(255) NULL,
      user_note text NULL,
      private_note text NULL
  );

ALTER TABLE
  public.entries
ADD
  CONSTRAINT entries_pkey PRIMARY KEY (eid)