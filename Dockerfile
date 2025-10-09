FROM python:3.12

WORKDIR /code

# Install dependencies first (for better caching)
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy app code
COPY ./app /code/app

# Expose port for FastAPI
EXPOSE 8000

# Use uvicorn with --reload for development (auto-reload on code changes)
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
