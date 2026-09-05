# Payment Service (ServiceWatch - Phase 1)

A realistic, lightweight payment microservice built using **Python, FastAPI, Pydantic, PostgreSQL, SQLAlchemy, and Alembic**.

---

## 📁 Project Structure

```text
payment-service/
├── alembic/
│   ├── env.py                              # Alembic migration environment config
│   ├── script.py.mako                      # Template for migration scripts
│   └── versions/
│       └── 001_create_payments_table.py   # Database migration for payments table
├── app/
│   ├── __init__.py                         # Marks app as a Python package
│   ├── config.py                           # App settings & environment loading
│   ├── database.py                         # SQLAlchemy engine & session factory
│   ├── models.py                           # SQLAlchemy database models
│   ├── schemas.py                          # Pydantic request/response schemas
│   └── main.py                             # FastAPI application & API endpoints
├── tests/
│   ├── __init__.py                         # Marks tests as a Python package
│   └── test_payments.py                    # Automated test suite (Pytest)
├── .env.example                            # Example environment variables
├── alembic.ini                             # Alembic configuration file
├── requirements.txt                        # Project dependencies
└── README.md                               # Documentation and usage guide
```

---

## 🚀 Getting Started

### 1. Create and Activate Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Database

Copy `.env.example` to `.env` and set your PostgreSQL connection URL:

```env
DATABASE_URL=postgresql://<username>:<password>@localhost:5432/<database_name>
```

### 4. Run Migrations

```powershell
alembic upgrade head
```

### 5. Start the Service

```powershell
uvicorn app.main:app --reload --port 8000
```

The service will run at `http://127.0.0.1:8000`.
Interactive Swagger UI documentation is available at `http://127.0.0.1:8000/docs`.

---

## 🧪 Running Tests

Run the test suite using `pytest`:

```powershell
pytest -v
```
