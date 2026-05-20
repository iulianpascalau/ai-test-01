from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import timedelta

import models
import auth
import orchestrator
import config
from database import engine, get_db

# Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Agentic Workspace API")

# CORS config for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, change to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Bootstrapping a default user for testing ---
def create_default_user(db: Session):
    user = db.query(models.User).filter(models.User.username == config.ADMIN_USERNAME).first()
    if not user:
        hashed_password = auth.get_password_hash(config.ADMIN_PASSWORD)
        new_user = models.User(username=config.ADMIN_USERNAME, hashed_password=hashed_password)
        db.add(new_user)
        db.commit()

@app.on_event("startup")
def startup_event():
    db = next(get_db())
    create_default_user(db)
# ------------------------------------------------

@app.post("/api/login")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/me")
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return {"username": current_user.username}

@app.get("/api/history")
def get_history(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    messages = db.query(models.Message).filter(models.Message.user_id == current_user.id).order_by(models.Message.timestamp.asc()).all()
    return [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp.strftime("%H:%M")
        }
        for msg in messages
    ]

class CommandRequest(BaseModel):
    command: str

@app.post("/api/command")
async def execute_command(req: CommandRequest, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Protected endpoint to submit a command to the Orchestrator."""
    user_msg = models.Message(user_id=current_user.id, role="user", content=req.command)
    db.add(user_msg)
    db.commit()
    
    result = await orchestrator.process_command(req.command)
    
    display_content = result.get("message") or str(result)
    agent_msg = models.Message(user_id=current_user.id, role="agent", content=display_content)
    db.add(agent_msg)
    db.commit()
    
    return result
