# app/routes/documents.py
# Document vault — upload, list, delete student documents

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
import httpx

from app.database import get_db
from app.models.user import User
from app.models.document import Document
from app.schemas.document import DocumentResponse, DocumentVault
from app.core.dependencies import get_current_user
from app.services.storage import upload_file, delete_file

router = APIRouter()

# Allowed document types
VALID_TYPES = {"cni", "releve", "attestation", "cv", "lettre", "photo", "autre"}

# Max file size: 5MB
MAX_FILE_SIZE = 5 * 1024 * 1024

# Allowed MIME types
ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/jpg",
}


# ============================================================
# GET /documents — List all my documents (the vault)
# ============================================================

@router.get("", response_model=DocumentVault)
def get_my_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the user's document vault with a completeness summary.
    The vault shows which essential documents are present/missing.
    This is used by the prep score to check document availability.
    """
    docs = db.query(Document).filter(
        Document.user_id == current_user.id,
    ).all()

    doc_types = {d.type for d in docs}
    essential = ["cv", "releve", "cni", "attestation"]
    filled = sum(1 for e in essential if e in doc_types)

    return DocumentVault(
        documents=[DocumentResponse.model_validate(d) for d in docs],
        has_cv="cv" in doc_types,
        has_releve="releve" in doc_types,
        has_cni="cni" in doc_types,
        has_attestation="attestation" in doc_types,
        completeness_pct=round((filled / len(essential)) * 100),
    )


# ============================================================
# POST /documents/upload — Upload a document
# ============================================================

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),                          # cni/releve/cv/etc.
    expires_at: Optional[str] = Form(None),            # Optional expiry date
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Uploads a document to Supabase Storage and saves metadata in DB.

    Flow:
    1. Validate file type and size
    2. Upload to Supabase Storage at path: user_id/doc_type_uuid.ext
    3. Save document metadata in DB (path, type, name)
    4. Return the document record

    The file itself lives in Supabase Storage.
    The DB only stores the path and metadata — stays lightweight.
    """

    # Validate document type
    if doc_type not in VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document type. Allowed: {', '.join(VALID_TYPES)}",
        )

    # Validate MIME type
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, JPG, and PNG files are allowed.",
        )

    # Read and validate file size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 5MB.",
        )

    # Build storage path: user_id/doctype_randomuuid.ext
    extension = file.filename.split(".")[-1] if "." in file.filename else "pdf"
    storage_path = f"{current_user.id}/{doc_type}_{uuid.uuid4()}.{extension}"

    # Upload to Supabase Storage
    try:
        file_url = await upload_file(
            file_bytes=file_bytes,
            file_path=storage_path,
            content_type=file.content_type,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}",
        )

    # Parse optional expiry date
    from datetime import date
    parsed_expiry = None
    if expires_at:
        try:
            parsed_expiry = date.fromisoformat(expires_at)
        except ValueError:
            pass  # Ignore invalid date format

    # Save metadata in DB
    doc = Document(
        user_id=current_user.id,
        type=doc_type,
        file_path=file_url,
        file_name=file.filename,
        is_valid=True,
        expires_at=parsed_expiry,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return DocumentResponse.model_validate(doc)


# ============================================================
# POST /documents/save-generated — Archiver un CV/lettre généré par l'IA
# ============================================================

class SaveGeneratedRequest(BaseModel):
    kind: str                       # "cv" | "lettre"
    title: str
    body: Optional[str] = None      # texte de la lettre
    cv: Optional[dict] = None       # CV structuré (CVResponse)


@router.post("/save-generated", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def save_generated(
    data: SaveGeneratedRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Génère un PDF (CV ou lettre) et l'archive dans le coffre-fort de l'étudiant."""
    from app.services.pdf import letter_pdf, cv_pdf

    author = current_user.full_name or "Candidat"
    if data.kind == "cv":
        contact = " - ".join(x for x in [current_user.email, current_user.phone, current_user.city] if x)
        pdf_bytes = cv_pdf(author, contact, data.cv or {})
        doc_type = "cv"
    elif data.kind == "lettre":
        pdf_bytes = letter_pdf(author, data.title, data.body or "")
        doc_type = "lettre"
    else:
        raise HTTPException(status_code=400, detail="kind doit être 'cv' ou 'lettre'.")

    safe = "".join(c for c in data.title if c.isalnum() or c in " -_").strip()[:40] or doc_type
    storage_path = f"{current_user.id}/{doc_type}_{uuid.uuid4()}.pdf"
    try:
        file_url = await upload_file(pdf_bytes, storage_path, "application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Échec de l'enregistrement : {str(e)}")

    doc = Document(
        user_id=current_user.id, type=doc_type,
        file_path=file_url, file_name=f"{safe}.pdf", is_valid=True,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return DocumentResponse.model_validate(doc)


# ============================================================
# POST /documents/{id}/analyze — L'IA lit le document (PDF) pour enrichir le profil
# ============================================================

@router.post("/{document_id}/analyze")
async def analyze_document_ai(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Télécharge le document, en extrait le texte (PDF) et l'analyse via l'IA pour
    proposer des informations (compétences, filière, niveau, moyenne) enrichissant
    le profil — ce profil enrichi améliore ensuite la génération de CV et lettres.
    """
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    if "pdf" not in (doc.file_name or "").lower() and "pdf" not in (doc.file_path or "").lower():
        raise HTTPException(status_code=400, detail="L'analyse IA ne supporte que les PDF pour le moment.")

    from app.services.storage import HEADERS
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(doc.file_path, headers=HEADERS)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Téléchargement impossible : {str(e)}")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Impossible de récupérer le document depuis le stockage.")

    from app.services.ai_coach import extract_pdf_text, analyze_document_text
    text = extract_pdf_text(resp.content)
    if len(text) < 40:
        raise HTTPException(
            status_code=422,
            detail="Ce document semble être un scan/image sans texte lisible. L'analyse nécessite un PDF contenant du texte.",
        )
    try:
        result = analyze_document_text(text, doc.type)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur IA : {str(e)}")
    return result


# ============================================================
# DELETE /documents/{id} — Delete a document
# ============================================================

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes a document from both Supabase Storage and the DB.
    Only the owner can delete their own documents.
    """
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,  # Security: owner only
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Extract storage path from the full URL
    # URL format: .../storage/v1/object/public/documents/USER_ID/filename
    storage_path = "/".join(doc.file_path.split("/")[-2:])

    # Delete from Supabase Storage
    await delete_file(storage_path)

    # Delete from DB
    db.delete(doc)
    db.commit()
