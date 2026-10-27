from fastapi.testclient import TestClient
from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.main import create_app
from apps.api.app.projects.catalog import CreativeAssetCatalog

def test_admin_can_create_and_bind_parent_and_parent_can_list_students(tmp_path):
    auth = AuthService({'admin': UserRecord('admin-1','org-1','organization_admin',hash_password('pw')), 'parent': UserRecord('parent-1','org-1','parent',hash_password('pw')), 'student': UserRecord('student-1','org-1','student',hash_password('pw'))}, storage_path=tmp_path/'auth.db')
    client = TestClient(create_app(auth)); admin_token = client.post('/auth/admin/login', json={'username':'admin','password':'pw'}).json()['accessToken']; headers={'Authorization':f'Bearer {admin_token}'}
    parent = client.post('/parent-portal/parents', headers=headers, json={'name':'家长','mobileMasked':'138****0000','parentId':'parent-1'}).json()
    client.post('/parent-portal/relations', headers=headers, json={'parentId':parent['parent_id'],'studentId':'student-1'}).raise_for_status()
    parent_token = client.post('/auth/login', json={'username':'parent','password':'pw'}).json()['accessToken']
    response = client.get('/parent-portal/students', headers={'Authorization':f'Bearer {parent_token}'})
    assert response.status_code == 200 and response.json() == {'students': ['student-1']}

def test_admin_can_publish_only_approved_student_work(tmp_path):
    auth = AuthService({'admin': UserRecord('admin-1','org-1','organization_admin',hash_password('pw')), 'student': UserRecord('student-1','org-1','student',hash_password('pw'))}, storage_path=tmp_path/'auth.db')
    assets = CreativeAssetCatalog(tmp_path/'assets.db')
    work = assets.create(project_id='project-1',organization_id='org-1',owner_user_id='student-1',kind='image',title='海洋',preview_url='',prompt='海洋')
    client = TestClient(create_app(auth,creative_asset_catalog=assets))
    token = client.post('/auth/admin/login', json={'username':'admin','password':'pw'}).json()['accessToken']
    headers = {'Authorization':f'Bearer {token}'}
    assert client.post(f'/parent-portal/works/{work.asset_id}/visibility',headers=headers,json={'visible':True}).status_code == 422
    assets.review(work.asset_id,'org-1','approved',False)
    response = client.post(f'/parent-portal/works/{work.asset_id}/visibility',headers=headers,json={'visible':True})
    assert response.status_code == 200 and response.json()['visible'] == 1

def test_parent_portal_rejects_cross_tenant_binding_and_private_work(tmp_path):
    auth = AuthService({
        'admin': UserRecord('admin-1','org-1','organization_admin',hash_password('pw')),
        'parent': UserRecord('parent-1','org-1','parent',hash_password('pw')),
        'student': UserRecord('student-1','org-1','student',hash_password('pw')),
        'foreign': UserRecord('student-2','org-2','student',hash_password('pw')),
    }, storage_path=tmp_path/'auth.db')
    assets = CreativeAssetCatalog(tmp_path/'assets.db')
    work = assets.create(project_id='p',organization_id='org-1',owner_user_id='student-1',kind='text',title='作品',preview_url='',prompt='',content='内容')
    client = TestClient(create_app(auth,creative_asset_catalog=assets))
    def headers(name):
        token = client.post('/auth/admin/login' if name == 'admin' else '/auth/login',json={'username':name,'password':'pw'}).json()['accessToken']
        return {'Authorization':f'Bearer {token}'}
    admin, parent = headers('admin'), headers('parent')
    account = client.post('/parent-portal/parents',headers=admin,json={'name':'家长','mobileMasked':'138****0000','parentId':'parent-1'}).json()
    assert client.post('/parent-portal/relations',headers=admin,json={'parentId':account['parent_id'],'studentId':'student-2'}).status_code == 404
    assert client.post('/parent-portal/relations',headers=admin,json={'parentId':account['parent_id'],'studentId':'student-1'}).status_code == 200
    assert client.get('/parent-portal/students/student-2/overview',headers=parent).status_code == 403
    assert client.get('/parent-portal/students/student-1/works',headers=parent).json() == {'works':[]}
    assert client.get(f'/parent-portal/students/student-1/works/{work.asset_id}',headers=parent).status_code == 404
    assert client.post('/parent-portal/notifications',headers=admin,json={'studentId':'student-2','title':'通知','content':'内容'}).status_code == 403
    assert client.post('/parent-portal/notifications',headers=admin,json={'studentId':'student-1','title':'通知','content':'内容'}).status_code == 200
    overview = client.get('/parent-portal/students/student-1/overview',headers=parent).json()
    assert overview['notifications'][0]['title'] == '通知'
