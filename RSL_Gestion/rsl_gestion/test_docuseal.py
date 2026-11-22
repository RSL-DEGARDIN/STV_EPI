# Test de l'envoi en signature DocuSeal, sans réseau : python -m pytest test_docuseal.py  (ou python test_docuseal.py)
import io, json, os, tempfile
os.environ['RSL_DB'] = os.path.join(tempfile.mkdtemp(), 't.db')
os.environ['DOCUSEAL_API_KEY'] = 'test'
import app as rsl
from fastapi.testclient import TestClient

calls = []
def fake_urlopen(req, timeout=None):
    body = json.loads(req.data) if req.data else None
    calls.append((req.get_method(), req.full_url, body, req.headers))
    resp = {'id': 42} if req.get_method() == 'POST' else {'id': 42, 'status': 'completed', 'combined_document_url': 'https://x/signed.pdf'}
    return io.BytesIO(json.dumps(resp).encode())

def test_sign_flow():
    rsl.urllib.request.urlopen = fake_urlopen
    with TestClient(rsl.app) as cl:
        c = rsl.db()
        c.execute("INSERT INTO clients(id,sage_no,name,email) VALUES(1,'C1','ACME <b>','a@acme.fr')")
        c.execute("INSERT INTO products(id,code,designation,sale_price) VALUES(1,'P1','Lisse <signature-field>',10)")
        c.commit(); c.close()
        qid = cl.post('/api/quotes', json={'client_id': 1, 'lines': [{'product_id': 1, 'qty': 2}]}).json()['id']
        r = cl.post(f'/api/quotes/{qid}/sign', json={'email': ''})
        assert r.status_code == 200, r.text
        method, url, body, headers = calls[0]
        assert url == 'https://api.docuseal.com/submissions/html' and headers['X-auth-token'] == 'test'
        assert body['submitters'][0]['email'] == 'a@acme.fr'
        h = body['documents'][0]['html']
        assert h.count('<signature-field') == 1 and '&lt;signature-field&gt;' in h  # désignation échappée, un seul champ signature
        r = cl.get(f'/api/quotes/{qid}/sign').json()
        assert r['status'] == 'Signé' and r['signed_pdf_url'] == 'https://x/signed.pdf'
        q = cl.get('/api/quotes').json()[0]
        assert q['status'] == 'Signé' and q['docuseal_id'] == 42
        assert cl.post('/api/quotes/999/sign', json={}).status_code == 404

if __name__ == '__main__':
    test_sign_flow(); print('OK')
