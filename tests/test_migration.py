import json,os,pathlib,sqlite3,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from migration import prepare_sqlite as m
from finance import ledger,web_queue,review_queue,manual_settlement
class MigrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.dir=pathlib.Path(self.tmp.name);self.src=self.dir/'source.db'
  c=sqlite3.connect(self.src);c.executescript('''CREATE TABLE users(id INTEGER PRIMARY KEY,email TEXT,password_hash TEXT,referral_code TEXT);CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER,csrf TEXT,expires INTEGER);INSERT INTO users VALUES(1,'a@example.test','hash-val','code');INSERT INTO sessions VALUES('h',1,'c',9999999999);''');c.commit();c.close()
 def tearDown(self):self.tmp.cleanup()
 def test_backup_and_rehearsal_preserve(self):
  before=m.inventory(self.src);back=self.dir/'backup.db';m.backup(self.src,back);self.assertEqual(before,m.inventory(back));dest=self.dir/'rehearsed.db';result=m.rehearsal(back,dest,'a@example.test');self.assertEqual(result['resultat'],'OK sur la copie');self.assertIn('CONFLIT',result['admin']);self.assertEqual(m.inventory(self.src),before)
  with self.assertRaises(FileExistsError):m.backup(self.src,back)
  self.assertEqual(before,m.inventory(back));self.assertEqual(os.stat(back).st_mode & 0o777,0o600)
 def test_missing_and_wrong_source(self):
  missing=self.dir/'not-exist.db';dest=self.dir/'dest.db'
  with self.assertRaises(FileNotFoundError):m.backup(missing,dest)
  self.assertFalse(missing.exists());self.assertFalse(dest.exists())
 def test_old_fee_gap_and_digest(self):
  web_queue.init(self.src);manual_settlement.init(self.src)
  ledger.book_verified_deposit(self.src,1,5000,'test-fund');ledger.reserve_withdrawal(self.src,1,2000,'w-old');review_queue.submit_reserved_withdrawal(self.src,'r-old','w-old')
  with sqlite3.connect(self.src) as c:c.execute('DROP TABLE withdrawal_fee_snapshot')
  before=m.inventory(self.src);self.assertEqual(before['legacy_pending_withdrawals_without_fee'],1)
  result=m.rehearsal(self.src,self.dir/'rehearsed.db',None);self.assertEqual(result['apres']['legacy_pending_withdrawals_without_fee'],1)
  self.assertEqual(m.inventory(self.src),before)
 def test_admin_conflict(self):
  self.assertIn('CONFLIT',m.admin_conflict(self.src,'a@example.test'))
  self.assertIn('aucun',m.admin_conflict(self.src,'b@example.test'))
if __name__=='__main__':unittest.main()
