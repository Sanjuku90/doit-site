import os, pathlib, sys, tempfile, unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import postgres_compat as adapter

class FakeCursor:
 def __init__(self):self.calls=[]
 def execute(self,sql,params=()):self.calls.append((sql,params))
 def fetchone(self):return None
 def fetchall(self):return []
 def fetchmany(self,*args):return []
 def __iter__(self):return iter(())

class FakeConnection:
 def __init__(self):self.cur=FakeCursor();self.autocommit=None
 def cursor(self):return self.cur
 def commit(self):pass
 def rollback(self):pass
 def close(self):pass

class PostgresCompatTests(unittest.TestCase):
 def test_begin_immediate_becomes_postgres_begin(self):
  raw=FakeConnection()
  with patch.object(adapter.psycopg2,'connect',return_value=raw):
   connection=adapter.Connection('postgresql://unused')
   connection.execute('BEGIN IMMEDIATE')
  self.assertEqual(raw.cur.calls[-1][0],'BEGIN')

 def test_table_info_pragma_queries_postgres_metadata(self):
  raw=FakeConnection()
  with patch.object(adapter.psycopg2,'connect',return_value=raw):
   connection=adapter.Connection('postgresql://unused')
   connection.execute('PRAGMA table_info(withdrawal_fee_snapshot)')
  sql,params=raw.cur.calls[-1]
  self.assertIn('information_schema.columns',sql)
  self.assertEqual(params,('withdrawal_fee_snapshot',))

 def test_explicit_local_path_never_uses_configured_database(self):
  with tempfile.TemporaryDirectory() as directory:
   path=str(pathlib.Path(directory)/'isolated.sqlite3')
   with patch.dict(os.environ,{'DATABASE_URL':'postgresql://unused'}):
    with patch.object(adapter.psycopg2,'connect') as postgres_connect:
     connection=adapter.connect(path)
     connection.execute('CREATE TABLE isolated (id INTEGER)')
     connection.close()
     postgres_connect.assert_not_called()

 def test_non_postgres_configured_url_fails_closed(self):
  with patch.dict(os.environ,{'DATABASE_URL':'./wrong-database.sqlite3','DOIT_TEST_SQLITE':'0'}):
   with self.assertRaises(RuntimeError):adapter.connect('./wrong-database.sqlite3')

if __name__=='__main__':unittest.main()
