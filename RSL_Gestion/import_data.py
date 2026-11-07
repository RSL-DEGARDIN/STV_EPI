import sqlite3, sys, os, re
from pathlib import Path
from openpyxl import load_workbook
BASE=Path(__file__).resolve().parent; DB=BASE/'data'/'rsl_gestion.db'; DB.parent.mkdir(exist_ok=True)
CLIENTS=Path(sys.argv[1]) if len(sys.argv)>1 else Path('../Clients.xlsx')
PRODUCTS=Path(sys.argv[2]) if len(sys.argv)>2 else Path('../produits euro.xlsx')
def val(x):
 if x is None:return None
 if isinstance(x,str):
  x=x.strip(); return x or None
 return x
def num(x):
 try:return float(str(x).replace(',','.').replace(' ','').replace('€','')) if x not in (None,'') else None
 except:return None
c=sqlite3.connect(DB); c.execute('PRAGMA foreign_keys=ON')
c.executescript('''CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY, sage_no TEXT UNIQUE, name TEXT, family TEXT, contact TEXT, address1 TEXT, address2 TEXT, postcode TEXT, city TEXT, phone TEXT, fax TEXT, email TEXT, delivery_name TEXT, delivery_address1 TEXT, delivery_address2 TEXT, delivery_postcode TEXT, delivery_city TEXT, billing_name TEXT, siret TEXT, billing_address1 TEXT, billing_address2 TEXT, billing_postcode TEXT, billing_city TEXT);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, code TEXT UNIQUE, supplier_ref TEXT, designation TEXT, color TEXT, weight REAL, list_price REAL, discount1 REAL, discount2 REAL, currency TEXT, purchase_price REAL, coefficient REAL, sale_price REAL, packaging TEXT, supplier_no TEXT, family TEXT, stock REAL DEFAULT 0, location TEXT, lead_time TEXT, stock_max REAL, stock_min REAL, backorder REAL);
CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY, supplier_no TEXT, name TEXT, UNIQUE(supplier_no,name));
CREATE TABLE IF NOT EXISTS supplier_products(id INTEGER PRIMARY KEY, product_id INTEGER, supplier_id INTEGER, supplier_ref TEXT, purchase_price REAL, currency TEXT, lead_time TEXT, is_preferred INTEGER DEFAULT 0, UNIQUE(product_id,supplier_id));''')
# Import clients; retain Sage client number exactly
if CLIENTS.exists():
 ws=load_workbook(CLIENTS,read_only=True,data_only=True).active; headers=[val(x) for x in next(ws.iter_rows(values_only=True))]; idx={str(h):i for i,h in enumerate(headers) if h}
 def get(r,k): return val(r[idx[k]]) if k in idx and idx[k]<len(r) else None
 for r in ws.iter_rows(min_row=2,values_only=True):
  no=get(r,'N° Client'); name=get(r,'Raison Sociale')
  if no is None or name is None: continue
  fields=[str(no),str(name),get(r,'famille'),get(r,'Responsable'),get(r,'Adresse1'),get(r,'Adresse2'),get(r,'code postal'),get(r,'Ville'),get(r,'Téléphone'),get(r,'Télécopie'),get(r,'email'),get(r,'raison sociale livraison'),get(r,'Adresse livraison1'),get(r,'Adresse livraison 2'),get(r,'code postal livrais'),get(r,'Ville livrais'),get(r,'raison sociale facturation'),get(r,'SIRET'),get(r,'Adresse facturation 1'),get(r,'Adresse facturation 2'),get(r,'code postal facturation'),get(r,'Ville facturation')]
  c.execute('INSERT OR IGNORE INTO clients(sage_no,name,family,contact,address1,address2,postcode,city,phone,fax,email,delivery_name,delivery_address1,delivery_address2,delivery_postcode,delivery_city,billing_name,siret,billing_address1,billing_address2,billing_postcode,billing_city) VALUES('+','.join('?'*22)+')',fields)
# Import product catalogue
if PRODUCTS.exists():
 ws=load_workbook(PRODUCTS,read_only=True,data_only=True).active; headers=[val(x) for x in next(ws.iter_rows(values_only=True))]; idx={str(h):i for i,h in enumerate(headers) if h}
 def get(r,k): return val(r[idx[k]]) if k in idx and idx[k]<len(r) else None
 for r in ws.iter_rows(min_row=2,values_only=True):
  code=get(r,'code article'); designation=get(r,'DESIGNATION')
  if code is None or designation is None: continue
  code=str(int(code)) if isinstance(code,(int,float)) and float(code).is_integer() else str(code)
  vals=[code,get(r,'REF fournisseur'),designation,get(r,'Coloris'),num(get(r,'POIDS Kgs')),num(get(r,'PRIX TARIF')),num(get(r,'Remise1(%)')),num(get(r,'Remise2(%)')),get(r,'devise'),num(get(r,'Prix_achat')),num(get(r,'Coefficient')),num(get(r,'Prix vente')),get(r,'Colisage'),get(r,'N°Fournisseur'),get(r,'FAMILLE'),num(get(r,'STOCKR')),get(r,'EMPLACEMENT'),get(r,'Delais approvisionnement'),num(get(r,'STOCKMAXI')),num(get(r,'STOCKMINI')),num(get(r,'Reliquat'))]
  # Duplicate article codes are deliberately skipped, never silently overwritten.
  c.execute('INSERT OR IGNORE INTO products(code,supplier_ref,designation,color,weight,list_price,discount1,discount2,currency,purchase_price,coefficient,sale_price,packaging,supplier_no,family,stock,location,lead_time,stock_max,stock_min,backorder) VALUES('+','.join('?'*21)+')',vals)
  # supplier master + supplier-specific item link when supplier number is present
  sn=val(get(r,'N°Fournisseur'))
  if sn is not None:
   c.execute('INSERT OR IGNORE INTO suppliers(supplier_no,name) VALUES(?,?)',(str(sn),f'Fournisseur {sn}'))
   sid=c.execute('SELECT id FROM suppliers WHERE supplier_no=?',(str(sn),)).fetchone()[0]
   pid=c.execute('SELECT id FROM products WHERE code=?',(code,)).fetchone()[0]
   c.execute('INSERT OR IGNORE INTO supplier_products(product_id,supplier_id,supplier_ref,purchase_price,currency,lead_time,is_preferred) VALUES(?,?,?,?,?,?,1)',(pid,sid,get(r,'REF fournisseur'),num(get(r,'Prix_achat')),get(r,'devise'),get(r,'Delais approvisionnement')))
c.commit()
print('Import terminé :',c.execute('select count(*) from clients').fetchone()[0],'clients,',c.execute('select count(*) from products').fetchone()[0],'articles,',c.execute('select count(*) from suppliers').fetchone()[0],'fournisseurs provisoires.')
print('Attention : les fournisseurs créés depuis N°Fournisseur sont des fiches provisoires à compléter avec l’export Sage.')
c.close()
