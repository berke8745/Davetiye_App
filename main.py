from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Date, Text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from datetime import date
from pydantic import BaseModel
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
    music_url = Column(String, nullable=True)
    envelope_text = Column(String, nullable=True)
    program_json = Column(Text, nullable=True)

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
            event_date=date(2027, 8, 15),
            location_name="Ritz-Carlton, İstanbul",
            maps_link="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3009.684139886477!2d28.9893998!3d41.0371457!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x14cab764fba211bf%3A0xe6ea6eb4b8da08df!2sThe%20Ritz-Carlton%2C%20Istanbul!5e0!3m2!1sen!2str!4v1713264627237!5m2!1sen!2str",
            story_text="Üniversitenin ilk yıllarında başlayan hikayemiz, zaman içinde büyüyerek en güzel günümüze dönüşüyor. Bu özel başlangıçta, heyecanımızı ve mutluluğumuzu paylaşmak için sizleri de aramızda görmekten onur duyacağız.",
            cover_image_url="https://images.unsplash.com/photo-1511285560929-80b456fea0bc?q=80&w=2069&auto=format&fit=crop",
            music_url="https://davetli.storage.googleapis.com/assets/audio-background/6831cbd8bc416e789c7f749f-1748093912554.mp3", # Test için referanstaki müzik
            envelope_text="Bir Etkinliğe Davet Edildiniz",
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
            
    # Return HTML template
    return templates.TemplateResponse(request=request, name="invitation.html", context={"couple": couple, "program": program_data})

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
