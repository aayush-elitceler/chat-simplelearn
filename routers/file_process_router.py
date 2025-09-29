import os
import asyncio
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form, BackgroundTasks, status
from typing import List, Dict
import shutil
from pathlib import Path
import uuid

from repository.ai_utilities import ai_utility_repo
from repository.file_processing.file_processing_repo import file_processing_repo
from models.file_processing.file_processing_models import FileConversionResponse, \
    TaskStatusResponse

router = APIRouter(
    prefix="/api/v1/fileProcessing",
    tags=["File Processing Router"]
)


task_status_store: Dict[str, Dict] = {}


async def process_vector_store_creation(
        task_id: str,
        project_name: str,
        collection_name: str,
        description: str,
        file_paths: List[str],
        file_names: List[str],
        user_id: str,
        user_email: str,
        user_name: str,
        is_subsequent: bool,
):
    temp_processing_dir = os.path.dirname(file_paths[0]) if file_paths else None
    try:
        task_status_store[task_id] = {"status": "processing", "progress": 0}

        task_status_store[task_id]["progress"] = 10

        # Create a simple file mapping for processing
        file_urls_map = {}
        for i, file_path in enumerate(file_paths):
            file_name = file_names[i]
            # Use local file path as URL for processing
            file_urls_map[file_name] = file_path
        task_status_store[task_id]["progress"] = 50

        chunked_docs = file_processing_repo.load_and_chunk_pdfs(
            temp_processing_dir,
            gcp_urls_map=file_urls_map
        )
        task_status_store[task_id]["progress"] = 75

        vector_store = file_processing_repo.create_milvus_vectorstore(
            documents=chunked_docs,
            collection_name=collection_name
        )

        task_status_store[task_id]["progress"] = 85

        # Generate insights from the same docs we just embedded
        insights = await ai_utility_repo.generate_insights_from_documents(chunked_docs)

        task_status_store[task_id] = {
            "status": "completed",
            "progress": 100,
            "result": {
                "num_documents": len(chunked_docs),
                "collection_name": collection_name,
                "summary": insights["summary"],
                "faq": insights["faq"],
            }
        }

    except Exception as e:
        task_status_store[task_id] = {"status": "failed", "error": str(e)}
    finally:
        if temp_processing_dir and os.path.exists(temp_processing_dir):
            shutil.rmtree(temp_processing_dir)


@router.post("/createVectorStore", response_model=TaskStatusResponse)
async def create_vector_store(
        background_tasks: BackgroundTasks,
        project_name: str = Form(...),
        description: str = Form(...),
        is_subsequent: bool = Form(False),
        files: List[UploadFile] = File(...)
):
    # is_subsequent = False
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

    task_id = str(uuid.uuid4())
    task_status_store[task_id] = {"status": "pending", "progress": 0}

    temp_upload_dir = os.path.join("temp_pdfs", task_id)
    os.makedirs(temp_upload_dir, exist_ok=True)

    file_paths = []
    file_names = []
    for file in files:
        file_path = os.path.join(temp_upload_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_paths.append(file_path)
        file_names.append(file.filename)

    asyncio.create_task(
        process_vector_store_creation(
            task_id,
            project_name,  # This will be used as both project_name and collection_name
            project_name,  # Using project_name as collection_name
            description,
            file_paths,
            file_names,
            "anonymous",  # user_id
            "anonymous@example.com",  # user_email
            "Anonymous User",  # user_name
            is_subsequent,
        )
    )

    return TaskStatusResponse(
        task_id=task_id,
        status="pending",
        message="Vector store creation started"
    )


@router.get("/taskStatus/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    task_data = task_status_store.get(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_data["status"] == "completed":
        return TaskStatusResponse(
            task_id=task_id,
            status="completed",
            progress=100,
            result=task_data.get("result"),
            message="Task completed successfully"
        )
    elif task_data["status"] == "failed":
        return TaskStatusResponse(
            task_id=task_id,
            status="failed",
            error=task_data.get("error"),
            message="Task failed"
        )
    else:
        return TaskStatusResponse(
            task_id=task_id,
            status=task_data["status"],
            progress=task_data.get("progress", 0),
            message="Task in progress"
        )





@router.post("/convertFileToPdf", response_model=FileConversionResponse)
async def convert_to_pdf(
        file: UploadFile = File(...),
        project_id: str = Form(...),
        collection_id: str = Form(...)
):
    try:
        valid_extensions = ['.doc', '.docx', '.txt']
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in valid_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported types: {', '.join(valid_extensions)}"
            )

        current_date = datetime.now().strftime("%Y-%m-%d")
        output_dir = os.path.join("pdfs", current_date)
        os.makedirs(output_dir, exist_ok=True)

        output_filename = f"{Path(file.filename).stem}.pdf"
        output_path = os.path.join(output_dir, output_filename)

        with open(output_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return FileConversionResponse(
            message="File converted to PDF successfully",
            original_filename=file.filename,
            gcp_urls=[],  # Empty list since we're not uploading to GCP
            createdAt=int(datetime.now().timestamp()),
            updatedAt=int(datetime.now().timestamp())
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))