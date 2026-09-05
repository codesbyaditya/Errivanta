from setuptools import setup, find_packages

setup(
    name="errivanta",
    version="0.2.0",
    description="Official Python SDK & FastAPI Middleware for Errivanta APM & Observability Platform",
    author="Errivanta Team",
    author_email="errivanta@gmail.com",
    url="https://github.com/codesbyaditya/errivanta",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
        "starlette>=0.36.0",
    ],
    python_requires=">=3.9",
)
