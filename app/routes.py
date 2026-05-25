from flask import Blueprint, request, jsonify
from app import db
from app.models import User, Project, ProjectMember, Collection, Document
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import json
from datetime import datetime

main = Blueprint('main', __name__)

# ── 회원가입 ──
@main.route('/api/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': '이미 존재하는 이름입니다'}), 400
    user = User(
        username=data['username'],
        password_hash=generate_password_hash(data['password']),
        email=data.get('email'),
        role='user'
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': '회원가입 완료'}), 201

# ── 로그인 ──
@main.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username']).first()
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({'error': '이름 또는 비밀번호가 틀렸습니다'}), 401
    token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    return jsonify({
        'token': token,
        'refresh_token': refresh_token,
        'username': user.username,
        'role': user.role
    })

# ── 내 정보 ──
@main.route('/api/me', methods=['GET'])
@jwt_required()
def me():
    user = User.query.get(int(get_jwt_identity()))
    return jsonify({'id': user.id, 'username': user.username, 'email': user.email, 'role': user.role})

# ── 프로젝트 생성 ──
@main.route('/api/projects', methods=['POST'])
@jwt_required()
def create_project():
    user_id = int(get_jwt_identity())
    data = request.json
    api_key = 'MARST-' + str(uuid.uuid4()).replace('-', '').upper()[:32]

    project = Project(
        name=data['name'],
        owner_id=user_id,
        api_key=api_key
    )
    db.session.add(project)
    db.session.flush()

    # owner 멤버로 자동 추가
    member = ProjectMember(
        project_id=project.id,
        user_id=user_id,
        tier='owner',
        can_read=True,
        can_write=True,
        can_setting=True
    )
    db.session.add(member)
    db.session.commit()

    return jsonify({'id': project.id, 'name': project.name, 'api_key': api_key}), 201

# ── 내 프로젝트 목록 ──
@main.route('/api/projects', methods=['GET'])
@jwt_required()
def get_projects():
    user_id = int(get_jwt_identity())
    members = ProjectMember.query.filter_by(user_id=user_id).all()
    projects = []
    for m in members:
        p = Project.query.get(m.project_id)
        projects.append({
            'id': p.id,
            'name': p.name,
            'api_key': p.api_key,
            'tier': m.tier,
            'created_at': p.created_at.isoformat()
        })
    return jsonify(projects)

# ── 프로젝트 멤버 티어 변경 (owner/admin만) ──
@main.route('/api/projects/<int:project_id>/members/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_member(project_id, user_id):
    me_id = int(get_jwt_identity())
    my_member = ProjectMember.query.filter_by(project_id=project_id, user_id=me_id).first()
    if not my_member or my_member.tier not in ['owner', 'admin']:
        return jsonify({'error': '권한 없음'}), 403

    member = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    if not member:
        return jsonify({'error': '멤버 없음'}), 404

    data = request.json
    if 'tier' in data: member.tier = data['tier']
    if 'can_read' in data: member.can_read = data['can_read']
    if 'can_write' in data: member.can_write = data['can_write']
    if 'can_setting' in data: member.can_setting = data['can_setting']
    db.session.commit()
    return jsonify({'message': '수정 완료'})

# ── API 키로 프로젝트 인증 ──
def get_project_from_key():
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return None
    return Project.query.filter_by(api_key=api_key).first()

# ── 컬렉션 목록 ──
@main.route('/api/db', methods=['GET'])
def db_get_collections():
    project = get_project_from_key()
    if not project:
        return jsonify({'error': 'API 키 없음'}), 401
    collections = Collection.query.filter_by(project_id=project.id).all()
    return jsonify([{'name': c.name, 'id': c.id} for c in collections])

# ── 문서 조회 ──
@main.route('/api/db/<collection_name>', methods=['GET'])
def db_get(collection_name):
    project = get_project_from_key()
    if not project:
        return jsonify({'error': 'API 키 없음'}), 401

    collection = Collection.query.filter_by(name=collection_name, project_id=project.id).first()
    if not collection:
        return jsonify([])

    docs = Document.query.filter_by(collection_id=collection.id).all()
    return jsonify([{
        'id': d.doc_id,
        'data': json.loads(d.data),
        'created_at': d.created_at.isoformat()
    } for d in docs])

# ── 문서 저장 ──
@main.route('/api/db/<collection_name>', methods=['POST'])
def db_set(collection_name):
    project = get_project_from_key()
    if not project:
        return jsonify({'error': 'API 키 없음'}), 401

    collection = Collection.query.filter_by(name=collection_name, project_id=project.id).first()
    if not collection:
        collection = Collection(name=collection_name, project_id=project.id)
        db.session.add(collection)
        db.session.flush()

    doc_id = str(uuid.uuid4())[:8].upper()
    doc = Document(
        collection_id=collection.id,
        doc_id=doc_id,
        data=json.dumps(request.json, ensure_ascii=False)
    )
    db.session.add(doc)
    db.session.commit()
    return jsonify({'id': doc_id, 'data': request.json}), 201

# ── 문서 삭제 ──
@main.route('/api/db/<collection_name>/<doc_id>', methods=['DELETE'])
def db_delete(collection_name, doc_id):
    project = get_project_from_key()
    if not project:
        return jsonify({'error': 'API 키 없음'}), 401

    collection = Collection.query.filter_by(name=collection_name, project_id=project.id).first()
    if not collection:
        return jsonify({'error': '컬렉션 없음'}), 404

    doc = Document.query.filter_by(collection_id=collection.id, doc_id=doc_id).first()
    if not doc:
        return jsonify({'error': '문서 없음'}), 404

    db.session.delete(doc)
    db.session.commit()
    return jsonify({'message': '삭제 완료'})
# ── 프로젝트 멤버 목록 조회 ──
@main.route('/api/projects/<int:project_id>/members', methods=['GET'])
@jwt_required()
def get_members(project_id):
    me_id = int(get_jwt_identity())
    my_member = ProjectMember.query.filter_by(project_id=project_id, user_id=me_id).first()
    if not my_member:
        return jsonify({'error': '권한 없음'}), 403

    members = ProjectMember.query.filter_by(project_id=project_id).all()
    result = []
    for m in members:
        user = User.query.get(m.user_id)
        result.append({
            'user_id': m.user_id,
            'username': user.username,
            'tier': m.tier,
            'can_read': m.can_read,
            'can_write': m.can_write,
            'can_setting': m.can_setting
        })
    return jsonify(result)

# ── 멤버 초대 (username으로) ──
@main.route('/api/projects/<int:project_id>/invite', methods=['POST'])
@jwt_required()
def invite_member(project_id):
    me_id = int(get_jwt_identity())
    my_member = ProjectMember.query.filter_by(project_id=project_id, user_id=me_id).first()
    if not my_member or my_member.tier not in ['owner', 'admin']:
        return jsonify({'error': '권한 없음'}), 403

    data = request.json
    user = User.query.filter_by(username=data['username']).first()
    if not user:
        return jsonify({'error': '사용자 없음'}), 404

    existing = ProjectMember.query.filter_by(project_id=project_id, user_id=user.id).first()
    if existing:
        return jsonify({'error': '이미 멤버입니다'}), 400

    member = ProjectMember(
        project_id=project_id,
        user_id=user.id,
        tier='guest',
        can_read=False,
        can_write=False,
        can_setting=False
    )
    db.session.add(member)
    db.session.commit()
    return jsonify({'message': f'{user.username} 초대 완료!'})

    from flask_jwt_extended import create_refresh_token, jwt_required, get_jwt_identity

# ── 토큰 재발급 ──
@main.route('/api/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    new_token = create_access_token(identity=user_id)
    return jsonify({'token': new_token})