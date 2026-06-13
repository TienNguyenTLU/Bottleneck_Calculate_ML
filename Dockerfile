# Use a lightweight official Python image
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory inside the container
WORKDIR /app

# Copy dependency definition first to leverage Docker build cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the remaining project files (app.py, model, static mappings, templates)
COPY . .

# Expose the Flask port
EXPOSE 5000

# Set Flask port environment variable
ENV PORT=5000

# Start Flask application
CMD ["python", "app.py"]
