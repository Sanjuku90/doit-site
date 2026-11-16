"""SQLite-shaped adapter backed by Supabase PostgreSQL in deployed mode.

Explicit local database paths use stdlib SQLite for isolated development and tests.
Production must pass a PostgreSQL URL through DATABASE_URL.
"""
import os, re
import sqlite3 as _sqlite3
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2 import Error as PgError, IntegrityError as PgIntegrityError, OperationalError as PgOperationalError

def _raise_database_error(error):
    if isinstance(error, PgIntegrityError):
        raise _sqlite3.IntegrityError('PostgreSQL integrity constraint failed') from error
    if isinstance(error, PgOperationalError):
        raise _sqlite3.OperationalError('PostgreSQL operation unavailable') from error
    if isinstance(error, PgError):
        raise _sqlite3.DatabaseError('PostgreSQL database operation failed') from error
    raise error

class Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int): return list(self.values())[key]
        return super().__getitem__(key)

class Cursor:
    def __init__(self, cur, lastrowid=None): self.cur=cur; self.lastrowid=lastrowid
    def fetchone(self):
        try: r=self.cur.fetchone()
        except PgError as error: _raise_database_error(error)
        return Row(r) if r is not None else None
    def fetchall(self):
        try: rows=self.cur.fetchall()
        except PgError as error: _raise_database_error(error)
        return [Row(r) for r in rows]
    def fetchmany(self, size=None):
        try: rows=self.cur.fetchmany(size) if size else self.cur.fetchmany()
        except PgError as error: _raise_database_error(error)
        return [Row(r) for r in rows]
    def __iter__(self):
        try:
            for r in self.cur: yield Row(r)
        except PgError as error: _raise_database_error(error)
    def __getattr__(self,n): return getattr(self.cur,n)

class Connection:
    def __init__(self, url):
        try: self.raw=psycopg2.connect(url, cursor_factory=DictCursor, connect_timeout=15)
        except PgError as error: _raise_database_error(error)
        self.raw.autocommit=False
    def __enter__(self): return self
    def __exit__(self, typ, val, tb):
        try:
            if typ: self.rollback()
            else: self.commit()
        finally: self.raw.close()
    def close(self): self.raw.close()
    def commit(self):
        try: self.raw.commit()
        except PgError as error: _raise_database_error(error)
    def rollback(self):
        try: self.raw.rollback()
        except PgError as error: _raise_database_error(error)
    def _cursor(self, sql, params=()):
        cur=self.raw.cursor()
        try: cur.execute(sql,params or ())
        except PgError as error: _raise_database_error(error)
        return cur
    def execute(self, sql, params=()):
        s=sql.strip()
        if s.upper().startswith('PRAGMA'):
            if 'TABLE_INFO' in s.upper():
                table=re.search(r'table_info\(([^)]+)\)',s,re.I).group(1).strip(" '\"")
                cur=self._cursor("SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",(table,)); return Cursor(cur)
            cur=self._cursor('SELECT 1'); return Cursor(cur)
        if s.upper() == 'BEGIN IMMEDIATE': s='BEGIN'
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
        cur=self._cursor(s,params)
        if ' RETURNING id' in s:
            try: row=cur.fetchone()
            except PgError as error: _raise_database_error(error)
            last=row[0] if row else None
        return Cursor(cur,last)
    def executemany(self, sql, seq):
        cur=self.raw.cursor()
        try: cur.executemany(sql.replace('?','%s'),seq)
        except PgError as error: _raise_database_error(error)
        return Cursor(cur)
    def executescript(self, script):
        # PostgreSQL trigger equivalent for the project's immutable-record guards.
        trigger_pat=re.compile(r"CREATE TRIGGER IF NOT EXISTS (\w+) BEFORE (UPDATE|DELETE) ON (\w+) BEGIN SELECT RAISE\(ABORT,'([^']*)'\); END;",re.I)
        for m in trigger_pat.finditer(script):
            name,event,table,msg=m.groups(); fn=f'{name}_fn'
            self.execute(f"CREATE OR REPLACE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION '{msg.replace(chr(39), chr(39)*2)}'; END; $$")
            self.execute(f'DROP TRIGGER IF EXISTS {name} ON {table}')
            self.execute(f'CREATE TRIGGER {name} BEFORE {event} ON {table} FOR EACH ROW EXECUTE FUNCTION {fn}()')
        script=trigger_pat.sub('',script)
        script=re.sub(r'PRAGMA\s+[^;]+;','',script,flags=re.I)
        script=re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\b','BIGSERIAL PRIMARY KEY',script,flags=re.I)
        # Run remaining DDL statements individually.
        for stmt in script.split(';'):
            if stmt.strip(): self.execute(stmt)

def connect(database=None, **kwargs):
    target=str(database).strip() if database is not None else ''
    configured=os.environ.get('DATABASE_URL','').strip()
    is_postgres=lambda value: value.lower().startswith(('postgres://','postgresql://'))
    if target and not is_postgres(target):
        if target==configured and os.environ.get('DOIT_TEST_SQLITE')!='1':
            raise RuntimeError('DATABASE_URL must be a PostgreSQL URL; local SQLite is test-only.')
        conn=_sqlite3.connect(target,**kwargs)
        conn.row_factory=_sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    url=target or configured
    if not url: raise RuntimeError('DATABASE_URL Supabase manquante dans les variables Render.')
    if not is_postgres(url): raise RuntimeError('DATABASE_URL doit être une URL PostgreSQL Supabase.')
    if '[YOUR-PASSWORD]' in url: raise RuntimeError('Remplacez [YOUR-PASSWORD] dans DATABASE_URL par le mot de passe PostgreSQL Supabase.')
    if re.search(r'[?&]sslmode=',url,re.I):
        url=re.sub(r'([?&])sslmode=[^&]*',r'\1sslmode=require',url,flags=re.I)
    else:
        url += ('&' if '?' in url else '?')+'sslmode=require'
    return Connection(url)

Error=_sqlite3.Error
IntegrityError=_sqlite3.IntegrityError
OperationalError=_sqlite3.OperationalError

class _SQLiteCompat:
    Error=Error; IntegrityError=IntegrityError; OperationalError=OperationalError; Row=Row
    connect=staticmethod(connect)

sqlite3=_SQLiteCompat()
