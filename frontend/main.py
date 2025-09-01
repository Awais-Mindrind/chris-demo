"""Frontend UI server using FastAPI + Jinja2."""
from fastapi import FastAPI, Request, Form
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import json
import os
from typing import Optional

app = FastAPI(title="Quote Agent UI", version="0.1.0")

# Configuration
BACKEND_BASE = os.getenv("BACKEND_BASE", "http://localhost:8000")
PORT = int(os.getenv("PORT", "8001"))

# Mount static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Templates
templates = Jinja2Templates(directory="frontend/templates")


@app.get("/")
async def index(request: Request):
    """Render the main chat page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/chat")
async def proxy_chat(request: Request):
    """Proxy chat requests to backend with SSE streaming."""
    # Get request body
    body = await request.json()
    
    async def stream_response():
        """Stream SSE response from backend."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:  # 120 second timeout for slow API responses
                # Forward request to backend
                async with client.stream(
                    "POST",
                    f"{BACKEND_BASE}/chat/stream",
                    json=body,
                    headers={"Accept": "text/event-stream"},
                    timeout=120.0
                ) as response:
                    # Stream chunks to browser
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except httpx.TimeoutException:
            # Handle timeout gracefully
            error_data = {
                "error": "Request timeout",
                "message": "The request took too long to complete. Please try again.",
                "session_id": body.get("session_id")
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        except httpx.RemoteProtocolError:
            # Handle connection errors
            error_data = {
                "error": "Connection error",
                "message": "Connection to backend was interrupted. Please try again.",
                "session_id": body.get("session_id")
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        except Exception as e:
            # Handle other errors
            error_data = {
                "error": "Proxy error",
                "message": f"Error: {str(e)}",
                "session_id": body.get("session_id")
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@app.post("/actions/create_quote")
async def proxy_create_quote(request: Request):
    """Proxy quote creation requests to backend."""
    # Get request body
    body = await request.json()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BACKEND_BASE}/actions/create_quote",
                json=body,
                headers={"Content-Type": "application/json"}
            )
            
            # Return backend response as-is
            return StreamingResponse(
                iter([response.content]),
                media_type="application/json",
                status_code=response.status_code
            )
    except httpx.TimeoutException:
        return StreamingResponse(
            iter([json.dumps({"error": "Request timeout", "message": "Quote creation took too long"})]),
            media_type="application/json",
            status_code=408
        )
    except Exception as e:
        return StreamingResponse(
            iter([json.dumps({"error": "Proxy error", "message": str(e)})]),
            media_type="application/json",
            status_code=500
        )


@app.get("/quotes/{quote_id}/pdf")
async def proxy_quote_pdf(quote_id: int):
    """Redirect to backend PDF endpoint."""
    return RedirectResponse(url=f"{BACKEND_BASE}/quotes/{quote_id}/pdf")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
