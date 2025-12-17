from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import aiofiles
import mimetypes

from app.services.pdf_converter import PDFConverter

app = FastAPI(title="PDF 黑白转换服务", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Initialize converter
converter = PDFConverter()

# Task storage (in production, use Redis or database)
tasks: Dict[str, Dict[str, Any]] = {}

# Ensure directories exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)


# Clean up old files periodically
@app.on_event("startup")
async def startup_event():
    # Clean up old files on startup
    converter.cleanup_old_files("uploads")
    converter.cleanup_old_files("outputs")

    # Schedule periodic cleanup
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(3600)  # Clean up every hour
            converter.cleanup_old_files("uploads")
            converter.cleanup_old_files("outputs")

    asyncio.create_task(periodic_cleanup())


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/convert")
async def convert_pdf(
    file: UploadFile = File(...),
    gray_levels: int = Form(2)
):
    """Convert PDF to grayscale"""
    # Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="只接受 PDF 文件")

    # Validate file size (50MB limit)
    file_size = 0
    content = await file.read()
    file_size = len(content)

    if file_size > 50 * 1024 * 1024:  # 50MB
        raise HTTPException(status_code=400, detail="文件大小超过 50MB 限制")

    # Validate gray_levels
    if gray_levels not in [1, 2, 3, 4]:
        raise HTTPException(status_code=400, detail="灰度档位必须是 1-4")

    # Generate task ID
    task_id = converter.generate_task_id()

    # Save uploaded file
    upload_filename = f"{task_id}.pdf"
    upload_path = os.path.join("uploads", upload_filename)

    async with aiofiles.open(upload_path, "wb") as f:
        await f.write(content)

    # Validate PDF
    if not converter.validate_pdf(upload_path):
        os.unlink(upload_path)
        raise HTTPException(status_code=400, detail="无效的 PDF 文件")

    # Get PDF page count
    try:
        page_count = converter.get_pdf_page_count(upload_path)
        if page_count > 100:
            os.unlink(upload_path)
            raise HTTPException(status_code=400, detail="PDF 页数超过 100 页限制")
    except Exception as e:
        os.unlink(upload_path)
        raise HTTPException(status_code=400, detail="无法读取 PDF 文件")

    # Create task record
    tasks[task_id] = {
        "status": "processing",
        "progress": 0,
        "page_count": page_count,
        "upload_path": upload_path,
        "output_path": os.path.join("outputs", f"{task_id}_converted.pdf"),
        "gray_levels": gray_levels,
        "error": None
    }

    # Start conversion in background
    asyncio.create_task(convert_pdf_background(task_id))

    return JSONResponse(content={
        "task_id": task_id,
        "status": "processing",
        "message": "PDF 转换已开始"
    })


async def convert_pdf_background(task_id: str):
    """Background task for PDF conversion"""
    try:
        task = tasks[task_id]
        upload_path = task["upload_path"]
        output_path = task["output_path"]
        gray_levels = task["gray_levels"]
        page_count = task["page_count"]

        # Update progress
        task["status"] = "converting"
        task["progress"] = 10

        # Convert PDF
        await converter.convert_pdf_async(upload_path, output_path, gray_levels)

        # Update task status
        task["status"] = "completed"
        task["progress"] = 100

    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"] = str(e)


@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    """Get conversion status"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    return JSONResponse(content={
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "page_count": task.get("page_count", 0),
        "error": task.get("error")
    })


@app.get("/api/download/{task_id}")
async def download_converted_pdf(task_id: str):
    """Download converted PDF"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="转换尚未完成")

    output_path = task["output_path"]
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="转换文件不存在")

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"converted_{task_id}.pdf"
    )


@app.get("/api/preview/{task_id}/{page}")
async def preview_page(
    task_id: str,
    page: int,
    preview_type: str = "original"
):
    """Preview original or converted PDF page"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    # Validate page number
    page_count = task.get("page_count", 0)
    if page < 1 or page > page_count:
        raise HTTPException(status_code=400, detail="页码无效")

    try:
        if preview_type == "original":
            # Original page preview - KEEP COLOR (do not convert to grayscale)
            image = converter.extract_pdf_page_color(
                task["upload_path"],
                page - 1,
                zoom=1.5
            )
        else:
            # Converted page preview (already grayscale)
            if task["status"] != "completed":
                raise HTTPException(status_code=400, detail="转换尚未完成")

            image = converter.convert_pdf_page_to_grayscale(
                task["output_path"],
                page - 1,
                task["gray_levels"],
                zoom=1.5
            )

        # Convert PIL Image to bytes
        import io
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        from fastapi.responses import Response
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览生成失败: {str(e)}")


@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    """Delete task and associated files"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    # Delete associated files
    try:
        if os.path.exists(task["upload_path"]):
            os.unlink(task["upload_path"])
        if os.path.exists(task["output_path"]):
            os.unlink(task["output_path"])
    except Exception:
        pass  # Ignore file deletion errors

    # Remove task from memory
    del tasks[task_id]

    return JSONResponse(content={"message": "任务已删除"})


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(content={"status": "healthy"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)