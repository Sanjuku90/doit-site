"""Small SQLite-shaped adapter backed exclusively by Supabase PostgreSQL.
It preserves the application's existing parameterized query API while using PostgreSQL.
"""
import os, re
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2 import Error, IntegrityError

class Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int): return list(self.values())[key]
        return super().__getitem__(key)

class Cursor:
    def __init__(self, cur, lastrowid=None): self.cur=cur; self.lastrowid=lastrowid
    def fetchone(self):
        r=self.cur.fetchone(); return Row(r) if r is not None else None
    def fetchall(self): return [Row(r) for r in self.cur.fetchall()]
    def fetchmany(self, size=None): return [Row(r) for r in (self.cur.fetchmany(size) if size else self.cur.fetchmany())]
    def __iter__(self):
        for r in self.cur: yield Row(r)
    def __getattr__(self,n): return getattr(self.cur,n)

class Connection:
    def __init__(self, url): self.raw=psycopg2.connect(url, cursor_factory=DictCursor, connect_timeout=15); self.raw.autocommit=False
    def __enter__(self): return self
    def __exit__(self, typ, val, tb):
        if typ: self.raw.rollback()
        else: self.raw.commit()
        self.raw.close()
    def close(self): self.raw.close()
    def commit(self): self.raw.commit()
    def rollback(self): self.raw.rollback()
    def execute(self, sql, params=()):
        s=sql.strip()
        if s.upper().startswith('PRAGMA'):
            if 'TABLE_INFO' in s.upper():
                table=re.search(r'table_info\(([^)]+)\)',s,re.I).group(1).strip(" '\"")
                cur=self.raw.cursor(); cur.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",(table,)); return Cursor(cur)
            cur=self.raw.cursor(); cur.execute('SELECT 1'); return Cursor(cur)
        s=s.replace('?', '%s')
        s=re.sub(r'\bRANDOM\(\)', 'random()', s, flags=re.I)
        if re.match(r'INSERT\s+OR\s+IGNORE\s+INTO',s,re.I):
            s=re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO','INSERT INTO',s,flags=re.I)+' ON CONFLICT DO NOTHING'
        last=None
        if re.match(r'INSERT\s+OR\s+REPLACE\s+INTO\s+fx_cache',s,re.I):
            s=re.sub(r'INSERT\s+OR\s+REPLACE\s+INTO','INSERT INTO',s,flags=re.I)
            s += ' ON CONFLICT (id) DO UPDATE SET rates_json=EXCLUDED.rates_json, source_timestamp=EXCLUDED.source_timestamp, fetched_at=EXCLUDED.fetched_at'
        if re.match(r'INSERT\s+INTO',s,re.I) and ' RETURNING ' not in s.upper():
            # Only tables with generated integer identifiers use lastrowid.
            table=re.match(r'INSERT\s+INTO\s+([a-z_]+)',s,re.I).group(1).lower()
            if table in {'users','audit','ledger','review_events','fin_transactions','fin_postings'}:
                s += ' RETURNING id'
        cur=self.raw.cursor(); cur.execute(s,params or ())
        if ' RETURNING id' in s:
            row=cur.fetchone(); last=row[0] if row else None
        return Cursor(cur,last)
    def executemany(self, sql, seq):
        cur=self.raw.cursor(); cur.executemany(sql.replace('?','%s'),seq); return Cursor(cur)
    def executescript(self, script):
        # PostgreSQL trigger equivalent for the project's immutable-record guards.
        # Les tables sont créées AVANT les triggers (sinon CREATE TRIGGER échoue sur une base vide).
        trigger_pat=re.compile(r"CREATE TRIGGER IF NOT EXISTS (\w+) BEFORE (UPDATE|DELETE) ON (\w+) BEGIN SELECT RAISE\(ABORT,'([^']*)'\); END;",re.I)
        triggers=trigger_pat.findall(script)
        script=trigger_pat.sub('',script)
        script=re.sub(r'PRAGMA\s+[^;]+;','',script,flags=re.I)
        script=re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\b','BIGSERIAL PRIMARY KEY',script,flags=re.I)
        # Run remaining DDL statements individually.
        for stmt in script.split(';'):
            if stmt.strip(): self.execute(stmt)
        for name,event,table,msg in triggers:
            fn=f'{name}_fn'
            self.execute(f"CREATE OR REPLACE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION '{msg.replace(chr(39), chr(39)*2)}'; END; $$")
            self.execute(f'DROP TRIGGER IF EXISTS {name} ON {table}')
            self.execute(f'CREATE TRIGGER {name} BEFORE {event} ON {table} FOR EACH ROW EXECUTE FUNCTION {fn}()')

def connect(database=None, **kwargs):
    url=os.environ.get('DATABASE_URL','').strip()
    if not url: raise RuntimeError('DATABASE_URL Supabase manquante dans les variables Render.')
    if '[YOUR-PASSWORD]' in url: raise RuntimeError('Remplacez [YOUR-PASSWORD] dans DATABASE_URL par le mot de passe PostgreSQL Supabase.')
    return Connection(url + ('&' if '?' in url else '?') + 'sslmode=require')

class _SQLiteCompat:
    Error=Error; IntegrityError=IntegrityError; Row=Row
    connect=staticmethod(connect)

sqlite3=_SQLiteCompat()
