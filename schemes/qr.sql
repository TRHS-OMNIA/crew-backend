CREATE TABLE
  public.qr (
    qrid character(16) NOT NULL,
    eid character(8) NOT NULL,
    uid character varying(32) NOT NULL,
    exp timestamp
    with
      time zone NOT NULL,
      scanned boolean NOT NULL DEFAULT false
  );

ALTER TABLE
  public.qr
ADD
  CONSTRAINT qr_pkey PRIMARY KEY (qrid)