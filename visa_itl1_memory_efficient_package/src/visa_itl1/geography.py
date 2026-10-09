import re,pandas as pd
NON=re.compile(r"[^A-Z0-9]")
def clean(s): return s.astype("string").str.upper().str.strip().str.replace(NON,"",regex=True).replace("",pd.NA)
def full(s):
 c=clean(s); return c.where(c.str.fullmatch(r"[A-Z]{1,2}[0-9][0-9A-Z]?[0-9][A-Z]{2}",na=False))
def area(s): return clean(s).str.extract(r"^([A-Z]{1,2})",expand=False).astype("string")
def district(s): return clean(s).str.extract(r"^([A-Z]{1,2}[0-9][0-9A-Z]?)",expand=False).astype("string")
def sector(s): return clean(s).str.extract(r"^([A-Z]{1,2}[0-9][0-9A-Z]?[0-9])",expand=False).astype("string")
def exact_area(s):
 c=clean(s); return c.where(c.str.fullmatch(r"[A-Z]{1,2}",na=False))
def exact_district(s):
 c=clean(s); return c.where(c.str.fullmatch(r"[A-Z]{1,2}[0-9][0-9A-Z]?",na=False))
def exact_sector(s):
 c=clean(s); return c.where(c.str.fullmatch(r"[A-Z]{1,2}[0-9][0-9A-Z]?[0-9]",na=False))
