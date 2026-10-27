from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.auth.access import TeachingAccess
from .service import ParentPortalStore

class ParentCreate(BaseModel): name:str; mobileMasked:str; parentId:str | None = None; username:str | None = None; password:str | None = None
class RelationCreate(BaseModel): parentId:str; studentId:str; relationship:str='监护人'
class VisibilityRequest(BaseModel): visible:bool=True
class FeedbackCreate(BaseModel): studentId:str; title:str; content:str; courseId:str|None=None; workId:str|None=None
class NoticeCreate(BaseModel): studentId:str|None=None; title:str; content:str

def create_parent_router(auth:AuthService, store:ParentPortalStore, courses=None, audit=None, learning=None, assets=None, classrooms=None):
    router=APIRouter(prefix='/parent-portal',tags=['parent-portal'])
    admin=require_role(require_session(auth),'organization_admin','platform_admin')
    teacher=require_role(require_session(auth),'teacher','organization_admin','platform_admin')
    parent=require_role(require_session(auth),'parent')
    access = TeachingAccess(auth, classrooms)
    @router.post('/parents')
    def create_parent(req:ParentCreate, session:SessionContext=Depends(admin)):
        parent_id = req.parentId
        if req.username and req.password:
            try: parent_id = auth.create_parent_user(username=req.username, password=req.password, organization_id=session.organization_id).user_id
            except ValueError as exc: raise HTTPException(422, str(exc)) from exc
        account = store.create_parent(session.organization_id,req.name,req.mobileMasked)
        if parent_id and parent_id != account.parent_id:
            replacement = type(account)(parent_id, account.organization_id, account.name, account.mobile_masked, account.status)
            store.accounts.pop(account.parent_id, None); store.accounts[parent_id] = replacement
            if store.path:
                with store._connect() as c:
                    c.execute("delete from parent_accounts where parent_id = ?", (account.parent_id,))
                    c.execute("insert or replace into parent_accounts values (?,?,?,?,?)", (replacement.parent_id,replacement.organization_id,replacement.name,replacement.mobile_masked,replacement.status))
            account = replacement
        return account.__dict__
    @router.post('/relations')
    def bind(req:RelationCreate, session:SessionContext=Depends(admin)):
        account = store.accounts.get(req.parentId)
        student = auth.user_for_id(req.studentId)
        if account is None or account.organization_id != session.organization_id or student is None or student.role != 'student' or student.organization_id != session.organization_id:
            raise HTTPException(404,'parent or student not found')
        return store.bind(req.parentId,req.studentId,req.relationship,session.user_id)
    @router.get('/students')
    def list_students(session:SessionContext=Depends(parent)):
        return {'students':store.students(session.user_id)}
    def check_student(student_id:str, session:SessionContext):
        account = store.accounts.get(session.user_id)
        student = auth.user_for_id(student_id)
        if not account or account.status != 'active' or account.organization_id != session.organization_id or not student or student.organization_id != session.organization_id or student_id not in store.students(session.user_id):
            raise HTTPException(403,'student access denied')
    @router.get('/students/{student_id}/overview')
    def overview(student_id:str, session:SessionContext=Depends(parent)):
        check_student(student_id,session); progress = learning.list_progress_for_student(student_id,session.organization_id) if learning else []
        progress_items = []
        for item in progress:
            course = None
            if courses:
                try: course = courses.get(item.course_id, session.organization_id)
                except (KeyError, PermissionError): pass
            progress_items.append({'courseId':item.course_id,'title':course.title if course else item.course_id,'summary':course.summary if course else '', 'lessons':list(course.lessons) if course else [], 'percent':item.percent,'completed':item.completed,'updatedAt':item.updated_at})
        return {'studentId':student_id,'progress':progress_items, 'feedback':store.feedback_for_student(session.organization_id,student_id), 'notifications':store.notifications_for_student(session.organization_id,student_id)}
    @router.get('/students/{student_id}/works')
    def works(student_id:str, session:SessionContext=Depends(parent)):
        check_student(student_id,session)
        items = assets.list_for_owner(student_id,session.organization_id) if assets else []
        return {'works':[{'workId':a.asset_id,'title':a.title,'kind':a.kind} for a in items if a.review_state == 'approved' and store.is_visible('work',a.asset_id)]}
    @router.get('/students/{student_id}/works/{work_id}')
    def work_detail(student_id:str, work_id:str, session:SessionContext=Depends(parent)):
        check_student(student_id,session)
        if not assets or not store.is_visible('work',work_id): raise HTTPException(404,'work not found')
        try: item = assets.get(work_id,session.organization_id)
        except (KeyError,PermissionError) as exc: raise HTTPException(404,'work not found') from exc
        if item.owner_user_id != student_id or item.review_state != 'approved': raise HTTPException(404,'work not found')
        return {'workId':item.asset_id,'title':item.title,'kind':item.kind,'content':item.content,'coverUrl':item.cover_url}
    @router.post('/works/{work_id}/visibility')
    def set_work_visibility(work_id:str, req:VisibilityRequest, session:SessionContext=Depends(teacher)):
        if not assets: raise HTTPException(404,'work not found')
        try: item = assets.get(work_id,session.organization_id)
        except (KeyError,PermissionError) as exc: raise HTTPException(404,'work not found') from exc
        access.require_student(session,item.owner_user_id)
        if req.visible and item.review_state != 'approved': raise HTTPException(422,'work must be approved first')
        return store.set_visibility('work',work_id,req.visible,session.user_id)
    @router.post('/feedback')
    def add_feedback(req:FeedbackCreate, session:SessionContext=Depends(teacher)):
        access.require_student(session,req.studentId)
        return store.add_feedback(session.organization_id,session.user_id,req.studentId,req.title,req.content,req.courseId,req.workId)
    @router.post('/notifications')
    def add_notification(req:NoticeCreate, session:SessionContext=Depends(teacher)):
        if not req.studentId: raise HTTPException(422,'studentId is required')
        access.require_student(session,req.studentId)
        return store.add_notification(session.organization_id,req.studentId,req.title,req.content)
    @router.get('/health')
    def health(): return {'status':'ready','ui':'not-released'}
    return router
