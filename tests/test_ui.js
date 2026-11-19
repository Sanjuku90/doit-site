// Unit tests of the real view-rendering functions with mocked API data, not browser E2E.
const fs=require('fs');const vm=require('vm');const assert=require('assert');
let source=fs.readFileSync('static/app.js','utf8');const marker='(async()=>{try{plans=';assert(source.includes(marker));source=source.slice(0,source.indexOf(marker));
const test=`
me={id:1,first_name:'Awa',last_name:'Test',email:'a@example.test',phone:'12345',display_currency:'USD',csrf:'csrf'};
const rows=[{id:'d-123',kind:'deposit',amount_usd_cents:10000,deposit_txid:'a'.repeat(64),state:'pending',created_at:'2026-11-12T12:00:00Z',destination:'<script>alert(1)</script>',declared_usdt:'100.000000'},{id:'r-456',kind:'withdrawal',amount_usd_cents:5000,state:'rejected',created_at:'2026-11-12T12:00:00Z',destination:'TAB1oeEKDS5NATwFAaUrTioDU9djX7anyS'}];
api=async p=>p==='/api/dashboard'?{entries:[],available_usd:0,invested_usd:0,reserved_usd:0,accrued_usd:0,commissions_usd:0,bonus_xof:5000}:p==='/api/manual/config'?{enabled:true,deposit_address:'TAB1oeEKDS5NATwFAaUrTioDU9djX7anyS'}:p==='/api/manual/requests'?{requests:rows}:Promise.reject(Error(p));
globalThis.__tests={
 nav:isAdmin=>{me={id:1,first_name:'Admin',is_admin:isAdmin};return frame('test')},
 destination:user=>loginDestination(user),
 history:async()=>{page='Historique';return await pageContent()},
 deposit:async()=>await manualPage(true),
 withdrawal:async()=>await manualPage(false),
 receipt:()=>receipt(rows[0]),
 withdrawalReceipt:()=>receipt(rows[1]),
};`;
const context=vm.createContext({document:{querySelector:()=>({})},location:{pathname:'/'},Intl,URL,URLSearchParams,console});vm.runInContext(source+test,context);
(async()=>{
 assert(context.__tests.nav(true).includes('data-go="Administration"'));
 assert(!context.__tests.nav(false).includes('data-go="Administration"'));
 assert.strictEqual(context.__tests.destination({is_admin:true}),'Administration');
 assert.strictEqual(context.__tests.destination({is_admin:false}),'Tableau de bord');
 let html=await context.__tests.history();assert(html.includes('Demandes'));assert(html.includes('d-123'));assert(html.includes('r-456'));assert(html.includes('receipt-area'));
 let deposit=await context.__tests.deposit();assert(deposit.includes('d-123'));assert(!deposit.includes('r-456'));assert(deposit.includes('Aucun contrôle sur chaîne'));
 let withdrawal=await context.__tests.withdrawal();assert(withdrawal.includes('r-456'));assert(!withdrawal.includes('d-123'));
 let receipt=context.__tests.receipt();assert(receipt.includes('Ce document n’est pas une preuve de paiement'));assert(receipt.includes('&lt;script&gt;'));assert(!receipt.includes('<script>'));assert(receipt.includes('TXID déclaré, non vérifié'));
 assert(context.__tests.withdrawalReceipt().includes('Rejeté'));
 console.log('UI rendering tests: OK (mocked API, no browser)');
})().catch(e=>{console.error(e);process.exit(1)});
