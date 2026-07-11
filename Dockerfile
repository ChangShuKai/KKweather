FROM python:3.10-slim

# Install system dependencies for satpy and pyresample (C-libraries)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libproj-dev \
    proj-data \
    proj-bin \
    libgeos-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements and install
# Note: requirements.txt is located at the project root based on the file structure
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend and frontend directories
COPY backend/ backend/
COPY frontend/ frontend/

# Expose the port FastAPI runs on
EXPOSE 8000

# Run the FastAPI server using Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
