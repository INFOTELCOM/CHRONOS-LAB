import importlib.util
import pathlib
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('chronos_app', ROOT / 'app.py')
chronos = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = chronos
spec.loader.exec_module(chronos)


def setup_client(tmp_path, monkeypatch):
    monkeypatch.setattr(chronos, 'DB', tmp_path / 'test.sqlite3')
    chronos.connect().close()
    c = chronos.connect()
    c.execute("INSERT INTO users(email,display_name,password_hash,role,workspace_id) VALUES(?,?,?,?,1)",
              ("admin@example.test", "Test Admin", chronos.generate_password_hash("VeryLong-Test-Password-2026!"), "admin"))
    user = c.execute("SELECT * FROM users WHERE email=?", ("admin@example.test",)).fetchone()
    token = "test-token-" + ("x" * 48)
    c.execute("INSERT INTO api_tokens(token_hash,user_id,expires_at) VALUES(?,?,?)",
              (chronos._token_digest(token), user["id"], (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()))
    c.commit()
    c.close()
    client = chronos.app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + token
    return client


def source(title, citation, locator):
    return {'title': title, 'citation': citation, 'url_or_doi': locator, 'source_type': 'publication'}


def test_health_and_scientific_policy(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    assert client.get('/api/health').status_code == 200
    policy = client.get('/api/scientific-policy').get_json()
    assert policy['automatic_scientific_validation'] is False
    assert policy['scientific_status'] == 'NOT_CERTIFIED_HYPOTHESIS'


def test_calendar_endpoint_and_invalid_correlation(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    ok = client.post('/api/calendar', json={'date': '2012-12-21', 'correlation': 584283})
    assert ok.status_code == 200
    assert 'long_count' in ok.get_json()
    bad = client.post('/api/calendar', json={'date': '2012-12-21', 'correlation': 1})
    assert bad.status_code == 400


def test_claim_requires_two_distinct_sources_and_never_certifies(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    payload = {'culture': 'Corpus de test', 'claim_type': 'identification', 'claim_text': 'Hypothèse de test',
               'sources': [source('Publication A', 'Auteur A, 2020, p. 1', '10.1000/example-a')]}
    assert client.post('/api/epigraphy/claims', json=payload).status_code == 400
    payload['sources'].append(source('Publication B', 'Auteur B, 2021, p. 2', '10.1000/example-b'))
    created = client.post('/api/epigraphy/claims', json=payload)
    assert created.status_code == 200
    claim_id = created.get_json()['id']
    claim = client.get(f'/api/epigraphy/claims/{claim_id}').get_json()
    assert claim['status'] == 'NEEDS_INDEPENDENT_REVIEW'
    assert 'CERTIFICATION' not in claim['status']


def test_reviews_require_distinct_declared_reviewers_and_status_is_not_certification(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    payload = {'culture': 'Corpus de test', 'claim_type': 'transcription', 'claim_text': 'Lecture hypothétique',
               'sources': [source('Publication A', 'Auteur A, 2020, p. 1', '10.1000/example-a'),
                           source('Publication B', 'Auteur B, 2021, p. 2', '10.1000/example-b')]}
    claim_id = client.post('/api/epigraphy/claims', json=payload).get_json()['id']
    review = {'reviewer_name': 'Relecteur A', 'affiliation': 'Institution déclarée', 'decision': 'AGREE',
              'rationale': 'Justification de test', 'references_checked': 'Publication A p. 1'}
    assert client.post(f'/api/epigraphy/claims/{claim_id}/reviews', json=review).status_code == 200
    assert client.post(f'/api/epigraphy/claims/{claim_id}/reviews', json=review).status_code == 409
    review['reviewer_name'] = 'Relecteur B'
    response = client.post(f'/api/epigraphy/claims/{claim_id}/reviews', json=review)
    assert response.status_code == 200
    assert response.get_json()['status'] == 'TWO_REVIEWS_RECORDED_NOT_SCIENTIFIC_CERTIFICATION'
    assert response.get_json()['identity_note']


def test_security_headers_and_cors_allowlist(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    monkeypatch.setenv('CHRONOS_ALLOWED_ORIGINS', 'https://infotelcom.github.io')
    response = client.get('/api/health', headers={'Origin': 'https://infotelcom.github.io'})
    assert response.headers.get('Access-Control-Allow-Origin') == 'https://infotelcom.github.io'
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
    denied = client.get('/api/health', headers={'Origin': 'https://untrusted.example'})
    assert denied.headers.get('Access-Control-Allow-Origin') is None


def test_auth_required_for_private_api(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    client.environ_base.pop("HTTP_AUTHORIZATION", None)
    response = client.get('/api/v2/experiments')
    assert response.status_code == 401
    assert response.get_json()['code'] == 'AUTH_REQUIRED'


def test_experiments_and_validations_persist_on_server(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    created = client.post('/api/v2/experiments', json={
        'name':'Essai de segmentation', 'model':'baseline', 'version':'v1',
        'dataset':'corpus-test-01', 'parameters':'threshold=0.5', 'notes':'hypothèse'
    })
    assert created.status_code == 201
    experiment_id = created.get_json()['id']
    assert client.get('/api/v2/experiments').get_json()[0]['id'] == experiment_id
    validation = client.post('/api/v2/validations', json={
        'model':'baseline-v1', 'dataset':'test-independent-v1',
        'precision':80, 'recall':75, 'f1':77.4, 'samples':40,
        'protocol':'Évaluation de test automatisée, rapport conservé.'
    })
    assert validation.status_code == 201
    assert client.get('/api/v2/validations').get_json()[0]['f1'] == 77.4


def test_evaluator_cannot_create_experiments(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    c = chronos.connect()
    c.execute("INSERT INTO users(email,display_name,password_hash,role,workspace_id) VALUES(?,?,?,?,1)",
              ("evaluator@example.test", "Evaluator", chronos.generate_password_hash("VeryLong-Test-Password-2026!"), "evaluator"))
    user = c.execute("SELECT * FROM users WHERE email=?", ("evaluator@example.test",)).fetchone()
    token = "evaluator-token-" + ("y" * 48)
    c.execute("INSERT INTO api_tokens(token_hash,user_id,expires_at) VALUES(?,?,?)",
              (chronos._token_digest(token), user["id"], (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()))
    c.commit(); c.close()
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + token
    response = client.post('/api/v2/experiments', json={'name':'X','model':'M','dataset':'D'})
    assert response.status_code == 403


def test_login_and_admin_user_creation(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    client.environ_base.pop("HTTP_AUTHORIZATION", None)
    response = client.post('/api/auth/login', json={
        'email':'admin@example.test', 'password':'VeryLong-Test-Password-2026!'
    })
    assert response.status_code == 200
    token = response.get_json()['token']
    assert len(token) >= 48
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + token
    created = client.post('/api/auth/users', json={
        'email':'researcher@example.test','display_name':'Chercheur Test',
        'password':'A-Strong-Research-Password-2026!','role':'researcher'
    })
    assert created.status_code == 201
    assert created.get_json()['user']['role'] == 'researcher'
