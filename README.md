# IDR-X: Intelligent Dead Reckoning Engine (SIH PS168)

Run backend:
    cd backend
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

Run frontend:
    cd frontend
    npm install
    npm run dev
