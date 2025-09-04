from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import _run
from FMCSA_LLM_PARSER import parse_fmcsa_with_llm
import json


app = FastAPI()

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DotRequest(BaseModel):
    dot_number: str
    tenant_id: str = None
    user_id: str = None
    mock: bool = True  # Add this field

@app.post("/vetting/dot")
async def process_fmsca_dot(request: DotRequest):
    context = {
        "tenant_id": request.tenant_id,
        "user_id": request.user_id
    }
    task_input = {
        "dot": request.dot_number,
        "mock": request.mock  # Pass mock flag to workflow
    }
    try:
        result = await _run(context, task_input)
        print("-----------------------")
        print(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@app.post("/fmsca/dot_parse")
async def parse_fmsca_dot(request: DotRequest):
    context = {
        "tenant_id": request.tenant_id,
        "user_id": request.user_id
    }
    task_input = {
        "dot": request.dot_number,
        "mock": request.mock
    }

    try:
        # 1️⃣ Run FMCSA workflow (raw JSON dict)
        json_result = await _run(context, task_input)

        # 2️⃣ Pass to LLM parser (it handles conversion itself)
        structured_output = parse_fmcsa_with_llm(json_result)

        # 3️⃣ structured_output is a JSON string, convert to dict for FastAPI
        return json.loads(structured_output)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
