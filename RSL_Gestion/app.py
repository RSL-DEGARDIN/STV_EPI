from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, os, io, csv, json, re
from datetime import datetime, date
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from openpyxl import load_workbook

BASE=Path(__file__).resolve().parent
DB=os.getenv('RSL_DB', str(BASE/'data'/'rsl_gestion.db'))
Path(DB).parent.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='RSL Gestion',version='0.2.0')
app.mount('/static',StaticFiles(directory=str(BASE/'static')),name='static')
templates=Jinja2Templates(directory=str(BASE/'templates'))

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init_db():
 c=db(); q=c.cursor()
 q.executescript('''
 CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY, sage_no TEXT UNIQUE, name TEXT, family TEXT, contact TEXT, address1 TEXT, address2 TEXT, postcode TEXT, city TEXT, phone TEXT, fax TEXT, email TEXT, delivery_name TEXT, delivery_address1 TEXT, delivery_address2 TEXT, delivery_postcode TEXT, delivery_city TEXT, billing_name TEXT, siret TEXT, billing_address1 TEXT, billing_address2 TEXT, billing_postcode TEXT, billing_city TEXT);
 CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, code TEXT UNIQUE, supplier_ref TEXT, designation TEXT, color TEXT, weight REAL, list_price REAL, discount1 REAL, discount2 REAL, currency TEXT, purchase_price REAL, coefficient REAL, sale_price REAL, packaging TEXT, supplier_no TEXT, family TEXT, stock REAL DEFAULT 0, location TEXT, lead_time TEXT, stock_max REAL, stock_min REAL, backorder REAL);
 CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY, supplier_no TEXT, name TEXT, family TEXT, contact TEXT, address1 TEXT, address2 TEXT, postcode TEXT, city TEXT, country TEXT, phone TEXT, fax TEXT, email TEXT, siret TEXT, vat_number TEXT, notes TEXT, UNIQUE(supplier_no,name));
 CREATE TABLE IF NOT EXISTS supplier_products(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), supplier_id INTEGER NOT NULL REFERENCES suppliers(id), supplier_ref TEXT, purchase_price REAL, currency TEXT, lead_time TEXT, is_preferred INTEGER DEFAULT 0, UNIQUE(product_id,supplier_id));
 CREATE TABLE IF NOT EXISTS quotes(id INTEGER PRIMARY KEY, number TEXT UNIQUE, client_id INTEGER REFERENCES clients(id), created TEXT, validity TEXT, status TEXT DEFAULT 'Brouillon', total REAL DEFAULT 0, notes TEXT);
 CREATE TABLE IF NOT EXISTS quote_lines(id INTEGER PRIMARY KEY, quote_id INTEGER REFERENCES quotes(id) ON DELETE CASCADE, product_id INTEGER REFERENCES products(id), code TEXT, designation TEXT, qty REAL, unit_price REAL, discount REAL DEFAULT 0, line_total REAL);
 CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, number TEXT UNIQUE, client_id INTEGER REFERENCES clients(id), quote_id INTEGER REFERENCES quotes(id), created TEXT, status TEXT DEFAULT 'Brouillon', total REAL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS order_lines(id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE, product_id INTEGER REFERENCES products(id), code TEXT, designation TEXT, qty REAL, delivered REAL DEFAULT 0, unit_price REAL, discount REAL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS purchase_orders(id INTEGER PRIMARY KEY, number TEXT UNIQUE, supplier_id INTEGER REFERENCES suppliers(id), created TEXT, status TEXT DEFAULT 'Brouillon');
 CREATE TABLE IF NOT EXISTS purchase_lines(id INTEGER PRIMARY KEY, purchase_id INTEGER REFERENCES purchase_orders(id) ON DELETE CASCADE, product_id INTEGER REFERENCES products(id), supplier_ref TEXT, designation TEXT, qty REAL, received REAL DEFAULT 0, purchase_price REAL);
 CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY, created TEXT, product_id INTEGER REFERENCES products(id), movement_type TEXT, quantity REAL, origin TEXT, user_name TEXT DEFAULT 'Admin', note TEXT);
 CREATE TABLE IF NOT EXISTS reservations(id INTEGER PRIMARY KEY, order_line_id INTEGER REFERENCES order_lines(id) ON DELETE CASCADE, product_id INTEGER REFERENCES products(id), qty REAL);
 CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY, number TEXT UNIQUE, order_id INTEGER REFERENCES orders(id), created TEXT, status TEXT DEFAULT 'Brouillon');
 CREATE TABLE IF NOT EXISTS delivery_lines(id INTEGER PRIMARY KEY, delivery_id INTEGER REFERENCES deliveries(id) ON DELETE CASCADE, order_line_id INTEGER REFERENCES order_lines(id), product_id INTEGER REFERENCES products(id), qty REAL);
 CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT);
 ''')
 # Migration des bases déjà créées en version 0.1
 existing={r['name'] for r in q.execute('PRAGMA table_info(suppliers)').fetchall()}
 for col in ['family','contact','address1','address2','postcode','city','country','phone','fax','email','siret','vat_number','notes']:
  if col not in existing: q.execute(f'ALTER TABLE suppliers ADD COLUMN {col} TEXT')
 c.commit(); c.close()

@app.on_event('startup')
def startup(): init_db()

def rows(sql,args=()):
 c=db(); r=c.execute(sql,args).fetchall(); c.close(); return [dict(x) for x in r]
def one(sql,args=()):
 c=db(); r=c.execute(sql,args).fetchone(); c.close(); return dict(r) if r else None
def nextnum(prefix,table):
 c=db(); n=c.execute(f'SELECT COUNT(*) n FROM {table}').fetchone()['n']+1; c.close(); return f'{prefix}-{datetime.now():%Y}-{n:05d}'
def reserved(product_id):
 r=one('SELECT COALESCE(SUM(qty),0) n FROM reservations WHERE product_id=?',(product_id,)); return float(r['n'])

@app.get('/',response_class=HTMLResponse)
def home(request:Request):
 stats={ 'clients':one('select count(*) n from clients')['n'], 'products':one('select count(*) n from products')['n'], 'quotes':one("select count(*) n from quotes where status!='Annulé'")['n'], 'orders':one("select count(*) n from orders where status!='Livrée' and status!='Annulée'")['n'], 'stock_alerts':one('select count(*) n from products where stock<=COALESCE(stock_min,0) and stock>0')['n'] }
 return templates.TemplateResponse('index.html',{'request':request,'stats':stats})

@app.get('/api/clients')
def clients(q:str=''):
 return rows('SELECT id,sage_no,name,postcode,city,phone,email FROM clients WHERE name LIKE ? OR sage_no LIKE ? ORDER BY name LIMIT 100',(f'%{q}%',f'%{q}%'))
@app.get('/api/products')
def products(q:str=''):
 return rows('''SELECT p.*, p.stock-COALESCE((SELECT SUM(r.qty) FROM reservations r WHERE r.product_id=p.id),0) available FROM products p WHERE code LIKE ? OR designation LIKE ? OR supplier_ref LIKE ? ORDER BY designation LIMIT 150''',(f'%{q}%',f'%{q}%',f'%{q}%'))
@app.get('/api/suppliers')
def suppliers(q:str=''):
 return rows('SELECT * FROM suppliers WHERE name LIKE ? OR supplier_no LIKE ? OR city LIKE ? ORDER BY name LIMIT 2000',(f'%{q}%',f'%{q}%',f'%{q}%'))

@app.post('/api/suppliers')
def create_supplier(payload:dict):
 name=(payload.get('name') or '').strip()
 if not name: raise HTTPException(400,'La raison sociale est obligatoire.')
 no=(payload.get('supplier_no') or '').strip() or None
 c=db(); cur=c.cursor()
 if no:
  existing=cur.execute('SELECT id FROM suppliers WHERE supplier_no=? ORDER BY id LIMIT 1',(no,)).fetchone()
  if existing:
   sid=existing['id']; cur.execute('UPDATE suppliers SET name=?,family=?,contact=?,address1=?,address2=?,postcode=?,city=?,country=?,phone=?,fax=?,email=?,siret=?,vat_number=?,notes=? WHERE id=?',(name,payload.get('family'),payload.get('contact'),payload.get('address1'),payload.get('address2'),payload.get('postcode'),payload.get('city'),payload.get('country'),payload.get('phone'),payload.get('fax'),payload.get('email'),payload.get('siret'),payload.get('vat_number'),payload.get('notes'),sid))
   c.commit(); c.close(); return {'id':sid,'updated':True}
 cur.execute('INSERT INTO suppliers(supplier_no,name,family,contact,address1,address2,postcode,city,country,phone,fax,email,siret,vat_number,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(no,name,payload.get('family'),payload.get('contact'),payload.get('address1'),payload.get('address2'),payload.get('postcode'),payload.get('city'),payload.get('country'),payload.get('phone'),payload.get('fax'),payload.get('email'),payload.get('siret'),payload.get('vat_number'),payload.get('notes')))
 sid=cur.lastrowid; c.commit(); c.close(); return {'id':sid,'created':True}

@app.put('/api/suppliers/{sid}')
def update_supplier(sid:int,payload:dict):
 name=(payload.get('name') or '').strip()
 if not name: raise HTTPException(400,'La raison sociale est obligatoire.')
 c=db(); cur=c.cursor()
 if not cur.execute('SELECT id FROM suppliers WHERE id=?',(sid,)).fetchone(): c.close(); raise HTTPException(404,'Fournisseur introuvable')
 no=(payload.get('supplier_no') or '').strip() or None
 if no and cur.execute('SELECT id FROM suppliers WHERE supplier_no=? AND id<>?',(no,sid)).fetchone(): c.close(); raise HTTPException(409,'Ce numéro fournisseur est déjà utilisé.')
 cur.execute('UPDATE suppliers SET supplier_no=?,name=?,family=?,contact=?,address1=?,address2=?,postcode=?,city=?,country=?,phone=?,fax=?,email=?,siret=?,vat_number=?,notes=? WHERE id=?',(no,name,payload.get('family'),payload.get('contact'),payload.get('address1'),payload.get('address2'),payload.get('postcode'),payload.get('city'),payload.get('country'),payload.get('phone'),payload.get('fax'),payload.get('email'),payload.get('siret'),payload.get('vat_number'),payload.get('notes'),sid))
 c.commit(); c.close(); return {'id':sid,'updated':True}

@app.post('/api/suppliers/import')
async def import_suppliers(file:UploadFile=File(...)):
 raw=await file.read(); filename=(file.filename or '').lower(); records=[]
 aliases={
  'supplier_no':['n° fournisseur','no fournisseur','numero fournisseur','numéro fournisseur','code fournisseur','n fournisseur','supplier_no','code'],
  'name':['raison sociale','nom fournisseur','fournisseur','nom','name','intitulé'],
  'family':['famille','famille fournisseur','type'], 'contact':['responsable','contact','interlocuteur'],
  'address1':['adresse1','adresse 1','adresse','address1'], 'address2':['adresse2','adresse 2','complément adresse'],
  'postcode':['code postal','codepostal','cp','postcode'], 'city':['ville','commune','city'], 'country':['pays','country'],
  'phone':['téléphone','telephone','tél','tel','phone'], 'fax':['télécopie','fax'], 'email':['email','e-mail','courriel'],
  'siret':['siret'], 'vat_number':['n° tva','numero tva','numéro tva','tva intracommunautaire','vat_number'], 'notes':['notes','commentaires','observations']}
 def norm(v):
  return re.sub(r'[^a-z0-9°]+',' ',str(v or '').strip().lower()).strip()
 try:
  if filename.endswith(('.xlsx','.xlsm')):
   ws=load_workbook(io.BytesIO(raw),read_only=True,data_only=True).active
   vals=list(ws.iter_rows(values_only=True))
  else:
   sample=raw[:4096].decode('utf-8-sig',errors='replace'); delim=';' if sample.count(';')>=sample.count(',') else ','
   vals=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace')),delimiter=delim))
  if not vals: raise ValueError('Fichier vide')
  headers=[norm(x) for x in vals[0]]; mapping={}
  for field,names in aliases.items():
   wanted={norm(x) for x in names}
   for i,h in enumerate(headers):
    if h in wanted: mapping[field]=i; break
  if 'name' not in mapping: raise ValueError('Colonne raison sociale / nom fournisseur introuvable.')
  for row in vals[1:]:
   d={k:(str(row[i]).strip() if i<len(row) and row[i] is not None else '') for k,i in mapping.items()}
   if d.get('name'): records.append(d)
 except Exception as e: raise HTTPException(400,f'Import impossible : {e}')
 c=db(); cur=c.cursor(); created=updated=skipped=0
 for d in records:
  no=d.get('supplier_no') or None
  if no:
   hit=cur.execute('SELECT id FROM suppliers WHERE supplier_no=? ORDER BY id LIMIT 1',(no,)).fetchone()
  else:
   hit=cur.execute('SELECT id FROM suppliers WHERE lower(trim(name))=lower(trim(?)) AND COALESCE(lower(trim(city)),'')=COALESCE(lower(trim(?)),'') ORDER BY id LIMIT 1',(d.get('name'),d.get('city'))).fetchone()
  fields=['name','family','contact','address1','address2','postcode','city','country','phone','fax','email','siret','vat_number','notes']
  vals2=[d.get(k) or None for k in fields]
  if hit:
   cur.execute('UPDATE suppliers SET '+','.join(f'{k}=?' for k in fields)+' WHERE id=?',(*vals2,hit['id'])); updated+=1
  else:
   cur.execute('INSERT INTO suppliers(supplier_no,'+','.join(fields)+') VALUES('+','.join('?'*(1+len(fields)))+')',(no,*vals2)); created+=1
 c.commit(); total=created+updated; c.close()
 return {'read':len(records),'created':created,'updated':updated,'skipped':skipped,'message':f'{total} ligne(s) traitée(s).'}
@app.get('/api/suppliers/{sid}/products')
def supplier_products(sid:int,q:str=''):
 return rows('''SELECT p.id,p.code,p.designation,p.stock,p.sale_price,p.purchase_price,p.supplier_ref AS default_ref,sp.supplier_ref,COALESCE(sp.purchase_price,p.purchase_price) AS supplier_price,sp.is_preferred FROM products p LEFT JOIN supplier_products sp ON sp.product_id=p.id AND sp.supplier_id=? WHERE (p.code LIKE ? OR p.designation LIKE ? OR p.supplier_ref LIKE ? OR sp.supplier_ref LIKE ?) ORDER BY p.designation LIMIT 100''',(sid,f'%{q}%',f'%{q}%',f'%{q}%',f'%{q}%'))
@app.get('/api/stock')
def stock(q:str=''):
 return rows('''SELECT p.id,p.code,p.designation,p.stock,COALESCE((SELECT SUM(qty) FROM reservations r WHERE r.product_id=p.id),0) reserved,p.stock-COALESCE((SELECT SUM(qty) FROM reservations r WHERE r.product_id=p.id),0) available,p.stock_min,p.location FROM products p WHERE code LIKE ? OR designation LIKE ? ORDER BY designation LIMIT 200''',(f'%{q}%',f'%{q}%'))

@app.post('/api/quotes')
def create_quote(payload:dict):
 c=db(); cur=c.cursor(); number=nextnum('DEV','quotes'); now=datetime.now().isoformat(timespec='minutes'); client_id=payload.get('client_id')
 cur.execute('INSERT INTO quotes(number,client_id,created,validity,notes) VALUES(?,?,?,?,?)',(number,client_id,now,payload.get('validity','30 jours'),payload.get('notes',''))); qid=cur.lastrowid; total=0
 for l in payload.get('lines',[]):
  p=cur.execute('SELECT * FROM products WHERE id=?',(l['product_id'],)).fetchone()
  if not p: c.rollback(); raise HTTPException(400,'Article introuvable')
  qty=float(l['qty']); price=float(l.get('unit_price',p['sale_price'] or 0)); disc=float(l.get('discount',0)); lt=qty*price*(1-disc/100); total+=lt
  cur.execute('INSERT INTO quote_lines(quote_id,product_id,code,designation,qty,unit_price,discount,line_total) VALUES(?,?,?,?,?,?,?,?)',(qid,p['id'],p['code'],p['designation'],qty,price,disc,lt))
 cur.execute('UPDATE quotes SET total=? WHERE id=?',(total,qid)); c.commit(); c.close(); return {'id':qid,'number':number,'total':total}

@app.post('/api/quotes/{qid}/convert')
def quote_to_order(qid:int):
 c=db(); cur=c.cursor(); q=cur.execute('SELECT * FROM quotes WHERE id=?',(qid,)).fetchone()
 if not q: c.close(); raise HTTPException(404,'Devis introuvable')
 lines=cur.execute('SELECT * FROM quote_lines WHERE quote_id=?',(qid,)).fetchall()
 if not lines: c.close(); raise HTTPException(400,'Devis sans ligne')
 number=nextnum('CMD','orders'); cur.execute('INSERT INTO orders(number,client_id,quote_id,created,total) VALUES(?,?,?,?,?)',(number,q['client_id'],qid,datetime.now().isoformat(timespec='minutes'),q['total'])); oid=cur.lastrowid
 for l in lines: cur.execute('INSERT INTO order_lines(order_id,product_id,code,designation,qty,unit_price,discount) VALUES(?,?,?,?,?,?,?)',(oid,l['product_id'],l['code'],l['designation'],l['qty'],l['unit_price'],l['discount']))
 c.commit(); c.close(); return {'id':oid,'number':number,'status':'Brouillon'}

@app.post('/api/orders/{oid}/validate')
def validate_order(oid:int):
 c=db(); cur=c.cursor(); order=cur.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
 if not order: c.close(); raise HTTPException(404,'Commande introuvable')
 if order['status']!='Brouillon': c.close(); raise HTTPException(400,'La commande doit être en brouillon')
 lines=cur.execute('SELECT * FROM order_lines WHERE order_id=?',(oid,)).fetchall(); insuff=[]
 for l in lines:
  p=cur.execute('SELECT stock FROM products WHERE id=?',(l['product_id'],)).fetchone(); r=cur.execute('SELECT COALESCE(SUM(qty),0) n FROM reservations WHERE product_id=?',(l['product_id'],)).fetchone()['n']; avail=float(p['stock'] or 0)-float(r or 0)
  if float(l['qty'])>avail: insuff.append(f"{l['code']} : {avail:g} disponible(s), {l['qty']:g} demandé(s)")
 if insuff: c.close(); raise HTTPException(409,detail={'message':'Stock insuffisant. Commande non validée.','articles':insuff})
 for l in lines: cur.execute('INSERT INTO reservations(order_line_id,product_id,qty) VALUES(?,?,?)',(l['id'],l['product_id'],l['qty']))
 cur.execute("UPDATE orders SET status='Validée' WHERE id=?",(oid,)); c.commit(); c.close(); return {'status':'Validée','number':order['number']}

@app.post('/api/deliveries')
def create_delivery(payload:dict):
 c=db(); cur=c.cursor(); oid=int(payload['order_id']); order=cur.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
 if not order or order['status'] not in ('Validée','Partiellement livrée'): c.close(); raise HTTPException(400,'Commande non validée')
 number=nextnum('BL','deliveries'); cur.execute('INSERT INTO deliveries(number,order_id,created,status) VALUES(?,?,?,?)',(number,oid,datetime.now().isoformat(timespec='minutes'),'Brouillon')); did=cur.lastrowid
 for item in payload.get('lines',[]):
  ol=cur.execute('SELECT * FROM order_lines WHERE id=? AND order_id=?',(item['order_line_id'],oid)).fetchone()
  if not ol: c.rollback(); c.close(); raise HTTPException(400,'Ligne de commande invalide')
  qty=float(item['qty']); remaining=float(ol['qty'])-float(ol['delivered'])
  if qty<=0 or qty>remaining: c.rollback(); c.close(); raise HTTPException(400,f"Quantité invalide pour {ol['code']} (reste {remaining:g})")
  cur.execute('INSERT INTO delivery_lines(delivery_id,order_line_id,product_id,qty) VALUES(?,?,?,?)',(did,ol['id'],ol['product_id'],qty))
 c.commit(); c.close(); return {'id':did,'number':number}

@app.post('/api/deliveries/{did}/validate')
def validate_delivery(did:int):
 c=db(); cur=c.cursor(); d=cur.execute('SELECT * FROM deliveries WHERE id=?',(did,)).fetchone()
 if not d or d['status']!='Brouillon': c.close(); raise HTTPException(400,'Bon de livraison invalide')
 lines=cur.execute('SELECT * FROM delivery_lines WHERE delivery_id=?',(did,)).fetchall()
 for l in lines:
  p=cur.execute('SELECT stock FROM products WHERE id=?',(l['product_id'],)).fetchone()
  if float(p['stock'] or 0)<float(l['qty']): c.rollback(); c.close(); raise HTTPException(409,'Stock physique insuffisant')
 for l in lines:
  cur.execute('UPDATE products SET stock=stock-? WHERE id=?',(l['qty'],l['product_id']))
  cur.execute('UPDATE order_lines SET delivered=delivered+? WHERE id=?',(l['qty'],l['order_line_id']))
  cur.execute('UPDATE reservations SET qty=MAX(0,qty-?) WHERE order_line_id=?',(l['qty'],l['order_line_id']))
  cur.execute('DELETE FROM reservations WHERE order_line_id=? AND qty<=0',(l['order_line_id'],))
  cur.execute('INSERT INTO stock_movements(created,product_id,movement_type,quantity,origin) VALUES(?,?,?,?,?)',(datetime.now().isoformat(timespec='minutes'),l['product_id'],'Livraison',-float(l['qty']),d['number']))
 cur.execute("UPDATE deliveries SET status='Validé' WHERE id=?",(did,))
 remaining=cur.execute('SELECT COUNT(*) n FROM order_lines WHERE order_id=? AND delivered<qty',(d['order_id'],)).fetchone()['n']
 cur.execute('UPDATE orders SET status=? WHERE id=?',('Partiellement livrée' if remaining else 'Livrée',d['order_id']))
 c.commit(); c.close(); return {'status':'Validé','remaining_lines':remaining}

@app.post('/api/purchases')
def create_purchase(payload:dict):
 c=db(); cur=c.cursor(); supplier=cur.execute('SELECT * FROM suppliers WHERE id=?',(payload['supplier_id'],)).fetchone()
 if not supplier: c.close(); raise HTTPException(404,'Fournisseur introuvable')
 number=nextnum('ACH','purchase_orders'); cur.execute('INSERT INTO purchase_orders(number,supplier_id,created) VALUES(?,?,?)',(number,supplier['id'],datetime.now().isoformat(timespec='minutes'))); pid=cur.lastrowid
 for l in payload.get('lines',[]):
  p=cur.execute('SELECT * FROM products WHERE id=?',(l['product_id'],)).fetchone()
  if not p: c.rollback(); c.close(); raise HTTPException(404,'Article introuvable')
  sref=l.get('supplier_ref') or p['supplier_ref']; price=float(l.get('purchase_price') or p['purchase_price'] or 0)
  cur.execute('INSERT INTO purchase_lines(purchase_id,product_id,supplier_ref,designation,qty,purchase_price) VALUES(?,?,?,?,?,?)',(pid,p['id'],sref,p['designation'],float(l['qty']),price))
  cur.execute('INSERT INTO supplier_products(product_id,supplier_id,supplier_ref,purchase_price,currency,is_preferred) VALUES(?,?,?,?,?,0) ON CONFLICT(product_id,supplier_id) DO UPDATE SET supplier_ref=excluded.supplier_ref,purchase_price=excluded.purchase_price',(p['id'],supplier['id'],sref,price,None))
 c.commit(); c.close(); return {'id':pid,'number':number}

@app.post('/api/purchases/{pid}/receive')
def receive_purchase(pid:int,payload:dict):
 c=db(); cur=c.cursor(); po=cur.execute('SELECT * FROM purchase_orders WHERE id=?',(pid,)).fetchone()
 if not po or po['status'] in ('Clôturée','Annulée'): c.close(); raise HTTPException(400,'Commande achat clôturée')
 recno=nextnum('BR','stock_movements')
 for item in payload.get('lines',[]):
  l=cur.execute('SELECT * FROM purchase_lines WHERE id=? AND purchase_id=?',(item['line_id'],pid)).fetchone()
  if not l: c.rollback(); c.close(); raise HTTPException(400,'Ligne achat invalide')
  qty=float(item['qty']); rest=float(l['qty'])-float(l['received'])
  if qty<=0 or qty>rest: c.rollback(); c.close(); raise HTTPException(400,f'Quantité reçue invalide (reste {rest:g})')
  cur.execute('UPDATE purchase_lines SET received=received+? WHERE id=?',(qty,l['id']))
  cur.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,l['product_id']))
  cur.execute('INSERT INTO stock_movements(created,product_id,movement_type,quantity,origin) VALUES(?,?,?,?,?)',(datetime.now().isoformat(timespec='minutes'),l['product_id'],'Réception fournisseur',qty,recno))
 remain=cur.execute('SELECT COUNT(*) n FROM purchase_lines WHERE purchase_id=? AND received<qty',(pid,)).fetchone()['n']
 cur.execute('UPDATE purchase_orders SET status=? WHERE id=?',('Partiellement réceptionnée' if remain else 'Réceptionnée',pid))
 c.commit(); c.close(); return {'receipt':recno,'status':'Partiellement réceptionnée' if remain else 'Réceptionnée'}

@app.get('/api/quotes')
def quote_list(): return rows('''SELECT q.*,c.name client FROM quotes q LEFT JOIN clients c ON c.id=q.client_id ORDER BY q.id DESC LIMIT 100''')
@app.get('/api/orders')
def order_list(): return rows('''SELECT o.*,c.name client FROM orders o LEFT JOIN clients c ON c.id=o.client_id ORDER BY o.id DESC LIMIT 100''')
@app.get('/api/purchases')
def purchase_list(): return rows('''SELECT p.*,s.name supplier FROM purchase_orders p LEFT JOIN suppliers s ON s.id=p.supplier_id ORDER BY p.id DESC LIMIT 100''')
@app.get('/api/movements')
def movements(): return rows('''SELECT m.*,p.code,p.designation FROM stock_movements m LEFT JOIN products p ON p.id=m.product_id ORDER BY m.id DESC LIMIT 150''')

@app.get('/api/orders/{oid}/lines')
def order_lines(oid:int):
 return rows("SELECT l.*,l.qty-l.delivered remaining FROM order_lines l WHERE order_id=?",(oid,))
@app.get('/api/purchases/{pid}/lines')
def purchase_lines(pid:int):
 return rows("SELECT l.*,l.qty-l.received remaining FROM purchase_lines l WHERE purchase_id=?",(pid,))

@app.get('/api/import-status')
def import_status(): return {'clients':one('select count(*) n from clients')['n'],'products':one('select count(*) n from products')['n'],'suppliers':one('select count(*) n from suppliers')['n']}

@app.get('/health')
def health(): return {'status':'ok','app':'RSL Gestion','version':'0.2.0'}

@app.get('/print/quote/{qid}',response_class=HTMLResponse)
def print_quote(qid:int):
 q=one('SELECT q.*,c.name client,c.address1,c.postcode,c.city FROM quotes q LEFT JOIN clients c ON c.id=q.client_id WHERE q.id=?',(qid,))
 if not q: raise HTTPException(404,'Devis introuvable')
 lines=rows('SELECT * FROM quote_lines WHERE quote_id=?',(qid,))
 html=f"<html><head><meta charset='utf-8'><title>{q['number']}</title><style>body{{font:14px Arial;margin:40px}}table{{width:100%;border-collapse:collapse;margin-top:30px}}td,th{{border-bottom:1px solid #ccc;padding:9px;text-align:left}}.right{{text-align:right}}</style></head><body><h1>RSL — DEVIS</h1><h2>{q['number']}</h2><p>Date : {q['created']}<br>Client : {q.get('client') or ''}<br>{q.get('address1') or ''} — {q.get('postcode') or ''} {q.get('city') or ''}</p><table><tr><th>Code article</th><th>Désignation</th><th>Qté</th><th>PU HT</th><th>Remise</th><th>Total HT</th></tr>"
 for l in lines: html+=f"<tr><td>{l['code']}</td><td>{l['designation']}</td><td>{l['qty']:g}</td><td>{l['unit_price']:.2f} €</td><td>{l['discount']:g}%</td><td>{l['line_total']:.2f} €</td></tr>"
 html+=f"</table><h2 class='right'>Total HT : {q['total']:.2f} €</h2><p>Validité : {q['validity']}</p><script>window.print()</script></body></html>"
 return HTMLResponse(html)
