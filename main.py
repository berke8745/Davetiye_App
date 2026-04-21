from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from sqlalchemy import create_engine, Column, Integer, String, Date, Text, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from datetime import date
from pydantic import BaseModel
import cloudinary
import cloudinary.uploader
import os

# Create Database and Tables
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./invitations.db")

# Render ve Supabase gibi servislerde postgres:// formatı gelirse postgresql:// olarak düzelt
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", "dac4dmqxa"),
    api_key=os.environ.get("CLOUDINARY_API_KEY", "158623156985392"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "AAFSLZYzZdZ3DjjQCDGJAXpm75I")
)

class Couple(Base):
    __tablename__ = "couples"
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)
    bride_name = Column(String)
    groom_name = Column(String)
    event_date = Column(Date)
    location_name = Column(String)
    maps_link = Column(String)
    story_text = Column(Text)
    cover_image_url = Column(String)
    story_image_url = Column(String, nullable=True)
    thankyou_image_url = Column(String, nullable=True)
    envelope_text = Column(String, nullable=True)
    program_json = Column(Text, nullable=True)
    # Yeni Hibrit Alanlar
    is_image_based = Column(Boolean, default=False)
    canva_image_url = Column(String, nullable=True)
    active_sections = Column(String, default='["story", "details", "timeline", "map", "rsvp"]')

class RSVP(Base):
    __tablename__ = "rsvps"
    id = Column(Integer, primary_key=True, index=True)
    couple_id = Column(Integer)
    guest_name = Column(String)
    guest_count = Column(Integer)
    attendance_status = Column(String)
    message = Column(Text)

Base.metadata.create_all(bind=engine)

# Setup FastAPI and Templates
app = FastAPI(title="Studio Printit Davetiye API")

# Ensure templates directory exists
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Note: we need to handle templates with Jinja2
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic Model for RSVP Post Data
class RSVPCreate(BaseModel):
    guest_name: str
    guest_count: int
    attendance_status: str
    message: str = ""

@app.on_event("startup")
def startup_event():
    # Insert Dummy Data for testing when app starts
    db = SessionLocal()
    if not db.query(Couple).filter(Couple.slug == "berke-eda").first():
        import json
        dummy_program = [
            {"time": "19:00", "event": "Karşılama ve Kokteyl"},
            {"time": "20:00", "event": "Nikah Merasimi"},
            {"time": "21:00", "event": "Düğün Yemeği"},
            {"time": "23:00", "event": "After Party"}
        ]
        
        dummy_couple = Couple(
            slug="berke-eda",
            bride_name="Eda",
            groom_name="Berke",
            event_date=date(2028, 6, 26),
            location_name="Eskisehir Tasigo Hotel",
            maps_link="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3066.684139886477!2d30.518!3d39.768!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zMznCsDQ2JzA0LjgiTiAzMMKwMzEnMDQuOCJF!5e0!3m2!1sen!2str!4v1713264627237!5m2!1sen!2str",
            story_text="We love each other so much...",
            cover_image_url="https://images.unsplash.com/photo-1519741497674-611481863552?q=80&w=2070&auto=format&fit=crop",
            story_image_url="https://images.unsplash.com/photo-1583939003579-730e3918a45a?q=80&w=1974&auto=format&fit=crop",
            thankyou_image_url="https://images.unsplash.com/photo-1515934751635-c81c6bc9a2d8?q=80&w=2070&auto=format&fit=crop",
            envelope_text="Eda & Berke Wedding",
            program_json=json.dumps(dummy_program)
        )
        db.add(dummy_couple)
        db.commit()
    db.close()

@app.get("/", include_in_schema=False)
def redirect_to_test():
    return RedirectResponse(url="/davetiye/berke-eda")

@app.get("/davetiye/{couple_slug}", response_class=HTMLResponse)
def read_invitation(request: Request, couple_slug: str, db: Session = Depends(get_db)):
    import json
    couple = db.query(Couple).filter(Couple.slug == couple_slug).first()
    
    if not couple:
        return HTMLResponse(content="<h1>Davetiye Bulunamadı.</h1><p>Girdiğiniz URL geçersiz olabilir.</p>", status_code=404)
    
    # Timeline verisini html içerisinde kolay çalışması için çözümlüyoruz
    program_data = []
    if couple.program_json:
        try:
            program_data = json.loads(couple.program_json)
        except:
            pass
            
    # Bölüm yönetimi verisini çözümlüyoruz
    active_sections = []
    if couple.active_sections:
        try:
            active_sections = json.loads(couple.active_sections)
        except:
            active_sections = ["story", "details", "timeline", "map", "rsvp"]
            
    # Return HTML template
    return templates.TemplateResponse(request=request, name="invitation.html", context={
        "couple": couple, 
        "program": program_data,
        "active_sections": active_sections
    })

@app.post("/api/davetiye/{couple_slug}/rsvp")
def create_rsvp(couple_slug: str, rsvp: RSVPCreate, db: Session = Depends(get_db)):
    couple = db.query(Couple).filter(Couple.slug == couple_slug).first()
    if not couple:
        raise HTTPException(status_code=404, detail="Davetiye bulunamadı.")
    
    db_rsvp = RSVP(
        couple_id=couple.id,
        guest_name=rsvp.guest_name,
        guest_count=rsvp.guest_count,
        attendance_status=rsvp.attendance_status,
        message=rsvp.message
    )
    db.add(db_rsvp)
    db.commit()
    return {"status": "success", "message": "Katılım durumunuz başarıyla iletildi."}

# --- ADMIN PANEL ---
security = HTTPBasic()

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, os.environ.get("ADMIN_PASSWORD", "printit"))
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, username: str = Depends(get_current_username), db: Session = Depends(get_db)):
    couples = db.query(Couple).order_by(Couple.id.desc()).all()
    for couple in couples:
        rsvps = db.query(RSVP).filter(RSVP.couple_id == couple.id).all()
        couple.total_rsvps = len(rsvps)
        couple.total_attending = sum([r.guest_count for r in rsvps if r.attendance_status == "Katılıyorum"])
        
    return templates.TemplateResponse(request=request, name="admin.html", context={"couples": couples})

@app.post("/admin/couple")
def create_couple(
    request: Request,
    slug: str = Form(...),
    bride_name: str = Form(...),
    groom_name: str = Form(...),
    event_date: str = Form(...),
    location_name: str = Form(None),
    maps_link: str = Form(None),
    story_text: str = Form(None),
    cover_image_url: str = Form(None),
    envelope_text: str = Form(None),
    program_json: str = Form(None),
    is_image_based: bool = Form(False),
    canva_image_url: str = Form(None),
    active_sections: str = Form('["story", "details", "timeline", "map", "rsvp"]'),
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db)
):
    from datetime import datetime
    try:
        parsed_date = datetime.strptime(event_date, "%Y-%m-%d").date()
    except Exception:
        parsed_date = datetime.now().date()
        
    new_couple = Couple(
        slug=slug.lower().replace(" ", "-"),
        bride_name=bride_name,
        groom_name=groom_name,
        event_date=parsed_date,
        location_name=location_name,
        maps_link=maps_link,
        story_text=story_text,
        cover_image_url=cover_image_url,
        envelope_text=envelope_text,
        program_json=program_json,
        is_image_based=is_image_based,
        canva_image_url=canva_image_url,
        active_sections=active_sections
    )
    db.add(new_couple)
    db.commit()
    
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/upload")
async def upload_image(file: UploadFile = File(...), username: str = Depends(get_current_username)):
    try:
        upload_result = cloudinary.uploader.upload(file.file, folder="davetiyeler")
        return {"url": upload_result.get("secure_url")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
